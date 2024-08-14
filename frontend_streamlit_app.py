import streamlit as st
import pandas as pd
import os
import json
import graphviz
import logging
import traceback
import alpha_algo_app

# Load parameters
PARAMETERS_PATH = "C:/projects/processMining/"
PARAMETERS_FILE_NAME = "parameters.json"
with open(os.path.join(PARAMETERS_PATH, PARAMETERS_FILE_NAME)) as f:
    param = json.load(f)
texts = param['texts']

# List CSV files in the specified folder
csv_files = [f for f in os.listdir(param["analysed_log_path"]) if f.endswith('.csv')]

st.set_page_config(page_title="Benchmarking Process Mining Algorithms", layout="wide")

def load_custom_css():
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .css-18e3th9 { padding: 1rem 2rem; }
        .css-1v0mbdj { background-color: #f0f2f6; }
        .css-1l02m9e { margin-bottom: 2rem; }
        .css-1l8nzb6 { font-size: 1.25rem; color: #333; }
        .css-1ljj8z7 { font-size: 1rem; color: #555; }
        .css-1k1yu2p { font-size: 0.9rem; color: #777; }
        .css-1g8m71y { border: 1px solid #ccc; }
        </style>
    """, unsafe_allow_html=True)


def display_traces_table(traces_dict):
    data = [[trace, metrics['count'], metrics['frequency']] for trace, metrics in traces_dict.items()]
    traces_df = pd.DataFrame(data, columns=['Sequence', 'Quantity', 'Frequency'])
    st.subheader("Traces Dictionary")
    st.dataframe(traces_df)

def display_directly_follows(directly_follows, min_frequency=1):
    dot = graphviz.Digraph('DirectlyFollows', format='png')
    dot.attr(dpi='65', fontsize='15', fontname='Helvetica')
    
    nodes = set(source for source, _ in directly_follows.keys()) | set(target for _, target in directly_follows.keys())
    
    for node in nodes:
        dot.node(node, shape='ellipse', style='filled', fillcolor='lightblue', fontsize='12')
    
    for (source, target), count in directly_follows.items():
        if count >= min_frequency:
            dot.edge(source, target, label=str(count), color='black', fontcolor='black', fontsize='10')

    st.subheader("Directly-Follows Relations")
    st.graphviz_chart(dot)

def serialize_data(data):
    if isinstance(data, dict):
        return {str(k) if isinstance(k, tuple) else k: serialize_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [serialize_data(i) for i in data]
    elif isinstance(data, (int, float, str, bool, type(None))):
        return data
    else:
        return str(data)

def display_data(title, data):
    st.subheader(title)
    serialized_data = serialize_data(data)
    if isinstance(serialized_data, (dict, list)):
        st.json(serialized_data)
    else:
        st.write(serialized_data)

def display_single_column_table(data, column_name, title):
    df = pd.DataFrame(data, columns=[column_name])
    st.subheader(title)
    st.dataframe(df)

def display_two_column_table(data, column_names, title):
    df = pd.DataFrame(data, columns=column_names)
    st.subheader(title)
    st.dataframe(df)

def display_footprint_matrix(footprint):
    if not footprint:
        st.subheader("Footprint Matrix")
        st.write("No footprint data available.")
        return
    
    events = sorted(set(event for pair in footprint.keys() for event in pair))
    matrix = pd.DataFrame(index=events, columns=events)
    
    for (event1, event2), value in footprint.items():
        matrix.loc[event1, event2] = value

    st.subheader("Footprint Matrix")
    st.dataframe(matrix, use_container_width=True)

def create_process_diagram(initial_events, final_events, nodes, filtered_transitions):
    """
    Creates a process diagram and displays it using Streamlit.
    Parameters:
        initial_events (set): Set of initial events.
        final_events (set): Set of final events.
        nodes (set): Set of all nodes in the process.
        filtered_transitions (dict): Dictionary with transitions and their relationships.
       
    Returns:
        str: The path to the generated process diagram PNG file.
    """
    dot = graphviz.Digraph(comment='Petri Net')
    dot.attr(rankdir='LR', size='16')
    # Node styles
    dot.attr('node', shape='rect', style='filled', color='black', fillcolor='white')
    
    # Add places (nodes)
    for node in nodes:
        if node not in ['start', 'end']:
            dot.node(node, node)
   
    # Add transitions and arcs
    for (source, target), relationship in filtered_transitions.items():  # Use .items() to iterate over dict
        source_str = '_'.join(source)  # Convert tuple to string
        target_str = '_'.join(target)  # Convert tuple to string
        
        if relationship == '| |':
            # Parallel Gateway, treat as transition with two outputs/inputs
            gateway_id = f'gateway_{source_str}_{target_str}'
            dot.node(gateway_id, shape='circle', label='+', style='filled', color='black', fillcolor='lightgrey')
            # Add arcs
            for s in source:
                dot.edge(s, gateway_id, dir='none')
            for t in target:
                dot.edge(gateway_id, t, dir='none')
        elif relationship == '-->':
            # Standard transition
            transition_id = f'transition_{source_str}_{target_str}'
            dot.node(transition_id, shape='circle', label='x', style='filled', color='black', fillcolor='lightgrey')
            for node in source:    
                dot.edge(node, transition_id)
            for node in target:
                dot.edge(transition_id, node)

    # Connect start events to initial events
    for event in initial_events:
        dot.node('start', 'start', shape='circle', style='filled', color='black', fillcolor='white')
        dot.edge('start', event)

    # Connect final events to end event
    for event in final_events:
        dot.node('end', 'end', shape='circle', style='filled', color='black', fillcolor='white', penwidth='3')
        dot.edge(event, 'end')

    # Render the diagram
    file_path = os.path.join(param['analysed_log_path'], 'process_diagram')
    dot.render(filename=file_path, format='png', cleanup=True)
    print(f"Process diagram has been generated as '{file_path}.png'")
   
    return f'{file_path}.png'


def start_analyser(selected_file, min_frequency=0):
    try:
        traces_dict = alpha_algo_app.read_log_file(selected_file)
        traces_dict = {trace: info for trace, info in traces_dict.items() if info['frequency'] >= min_frequency}
        
        initial_events, final_events = alpha_algo_app.identify_initial_and_final_events(traces_dict)
        nodes = alpha_algo_app.identify_all_nodes(traces_dict)
        directly_follows = alpha_algo_app.compute_directly_follows(traces_dict, initial_events, final_events)
        footprint = alpha_algo_app.create_footprint(directly_follows)
        independent_sets = alpha_algo_app.find_independent_sets(footprint)
        transitions = alpha_algo_app.find_transitions(footprint, independent_sets)
        filtered_transitions = alpha_algo_app.filter_maximal_sets(transitions)

        display_traces_table(traces_dict)
        display_directly_follows(directly_follows)
        display_single_column_table(nodes, 'Nodes', 'Nodes')
        display_single_column_table(initial_events, 'Initial Events', 'Initial Events')
        display_single_column_table(final_events, 'Final Events', 'Final Events')
        display_footprint_matrix(footprint)

        flattened_independent_data = [' ; '.join(sorted(list(item))) for item in independent_sets]
        display_single_column_table(flattened_independent_data, 'Independent Sets', 'Independent Sets')

        # Convert transitions to list of tuples
        transitions_tuples = list(transitions.items())
        display_two_column_table(transitions_tuples, ('Sequence', 'Transition'), 'Transitions')
        
        # Convert filtered transitions to list of tuples
        filtered_transitions_tuples = list(filtered_transitions.items())
        display_two_column_table(filtered_transitions_tuples, ('Filtered Sequence', 'Transition'), 'Filtered Transitions')

        diagram_path = create_process_diagram(initial_events, final_events, nodes, filtered_transitions)
        st.image(diagram_path, caption='Process Diagram', use_column_width=False)
        
    except Exception as e:
        logging.error(f"An error occurred while processing file: {selected_file} {e}\n{traceback.format_exc()}")
        st.error(f"An error occurred while processing the file. Please check the logs for more details.")

def design_page():

    load_custom_css()

    st.sidebar.title("Alpha Miner Algorithm")
    st.sidebar.subheader("Benchmarking Process Mining Algorithms")
    st.sidebar.write("Developed by Mahmoud TULAIMAT")

    selected_file = st.sidebar.selectbox("Choose a CSV file", csv_files)
    st.sidebar.write("Log files path : ", param["analysed_log_path"])
    st.sidebar.write("Selected file :", selected_file)

    min_frequency_input = st.sidebar.text_input("Enter the min_frequency:", "0")
    
    try:
        min_frequency = float(min_frequency_input.replace(',', '.'))
        if min_frequency > 100:
            min_frequency %= 100
            st.sidebar.write(f"For you, I got your value modulo hundred) ;-) {min_frequency}")
        if min_frequency > 1:
            min_frequency /= 100
            st.sidebar.write(f"For you, I divided your value by hundred) ;-) {min_frequency}")
    except ValueError:
        st.sidebar.error("Please enter a valid number for the min_frequency.")
        min_frequency = 0

    if st.sidebar.button("Start Analysis"):
        st.write(f"Processing file: {selected_file} with min_frequency = {min_frequency}")
        start_analyser(selected_file, min_frequency)
    
    st.sidebar.subheader("About the Thesis")
    st.sidebar.write(texts['left_block_author_refs'])


if __name__ == "__main__":
    design_page()