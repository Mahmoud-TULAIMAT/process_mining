import pandas as pd
import re
import logging
import json
import os
import traceback
import networkx as nx
import matplotlib.pyplot as plt
from itertools import product, combinations
import uuid
import time
from bpmn_python import bpmn_diagram_rep as bpmn

# Configuration
PARAMETERS_PATH = "C:/projects/processMining/"
PARAMETERS_FILE_NAME = "parameters.json"

def read_parameters(file_path):
    """Reads parameters from a JSON file."""
    with open(file_path, 'r') as file:
        return json.load(file)

# Read parameters
param = read_parameters(os.path.join(PARAMETERS_PATH, PARAMETERS_FILE_NAME))

# Configure logging
THIS_SCRIPT_LOG_PATH = os.path.join(PARAMETERS_PATH, param['log_file_name'])
logging.basicConfig(filename=THIS_SCRIPT_LOG_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

def read_log_file(analysed_file_name: str):
    """
    Reads a CSV log file and returns a dictionary of trace frequencies.
    
    Parameters:
        analysed_file_name (str): Path to the log file.

    Returns:
        dict: Trace dictionary with frequencies.
    """
    analysed_log = os.path.join(param['analysed_log_path'], analysed_file_name)
    df_log = pd.read_csv(analysed_log, usecols=['case_id', 'activity_name', 'timestamp'])
    df_log['timestamp'] = pd.to_datetime(df_log['timestamp'])
    df_grouped = df_log.sort_values(by=['case_id', 'timestamp']) \
                       .groupby('case_id')['activity_name'] \
                       .apply(list) \
                       .reset_index(name='trace')
    df_grouped['trace'] = df_grouped['trace'].apply(tuple)
    trace_counts = df_grouped['trace'].value_counts()
    trace_dict = trace_counts.to_dict()
    return {trace: {'count': count, 'frequency': count / len(df_grouped)} for trace, count in trace_dict.items()}

def identify_all_nodes(trace_dict):
    """
    Identifies all nodes including start and end events.
    
    Parameters:
        trace_dict (dict): Dictionary of traces.

    Returns:
        list: List of all nodes.
    """
    nodes = ['start']
    for trace in trace_dict.keys():
        nodes.extend(event for event in trace if event not in nodes)
    nodes.append('end')
    return nodes

def identify_initial_and_final_events(trace_dict):
    """
    Identifies initial and final events from traces.
    
    Parameters:
        trace_dict (dict): Dictionary of traces.

    Returns:
        tuple: Lists of initial and final events.
    """
    initial_events = {trace[0] for trace in trace_dict.keys()}
    final_events = {trace[-1] for trace in trace_dict.keys()}
    return list(initial_events), list(final_events)

def compute_directly_follows(trace_dict, start_events, end_events):
    """
    Computes directly-follows relations including start and end events.
    
    Parameters:
        trace_dict (dict): Dictionary of traces.
        start_events (set): Set of start events.
        end_events (set): Set of end events.

    Returns:
        dict: Directly-follows relations with counts.
    """
    directly_follows = {}
    start_events = set(start_events)
    end_events = set(end_events)
    
    for trace, metrics in trace_dict.items():
        qty = metrics.get('count', 0)
        if not isinstance(qty, int):
            raise ValueError(f"Count for trace {trace} is not an integer: {qty}")
        
        if trace[0] in start_events:
            directly_follows[('start', trace[0])] = directly_follows.get(('start', trace[0]), 0) + qty
        
        for i in range(len(trace) - 1):
            pair = (trace[i], trace[i + 1])
            directly_follows[pair] = directly_follows.get(pair, 0) + qty
        
        if trace[-1] in end_events:
            directly_follows[(trace[-1], 'end')] = directly_follows.get((trace[-1], 'end'), 0) + qty
    
    return directly_follows

def create_footprint(directly_follows):
    """
    Creates a footprint representation of activity relationships.
    
    Parameters:
        directly_follows (dict): Directly-follows relations.

    Returns:
        dict: Footprint representation.
    """
    footprint = {}
    activities = {a for a, b in directly_follows.keys() if a not in {'start', 'end'}}
    activities.update(b for a, b in directly_follows.keys() if b not in {'start', 'end'})
    
    for a in activities:
        for b in activities:
            if a == b:
                footprint[(a, b)] = "| |" if (a, a) in directly_follows else " # "
            else:
                follows_ab = (a, b) in directly_follows
                follows_ba = (b, a) in directly_follows
                if follows_ab and follows_ba:
                    footprint[(a, b)] = "| |"
                elif follows_ab:
                    footprint[(a, b)] = "-->"
                elif follows_ba:
                    footprint[(a, b)] = "<--"
                else:
                    footprint[(a, b)] = " # "
    
    return footprint

def is_independent_set(footprint_matrix, group_of_events):
    """
    Checks if a set of events is independent.
    
    Parameters:
        footprint_matrix (dict): Footprint matrix.
        group_of_events (list): List of events.

    Returns:
        bool: True if independent, otherwise False.
    """
    for i in range(len(group_of_events)):
        for j in range(i + 1, len(group_of_events)):
            a, b = group_of_events[i], group_of_events[j]
            if footprint_matrix.get((a, b), ' # ') != ' # ' or footprint_matrix.get((b, a), ' # ') != ' # ':
                return False
    return True

def find_independent_sets(footprint_matrix):
    """
    Finds independent sets of events based on the footprint matrix.
    
    Parameters:
        footprint_matrix (dict): Footprint matrix.

    Returns:
        list: List of independent sets.
    """
    independent_sets = []
    events = {a for (a, b) in footprint_matrix.keys()} | {b for (a, b) in footprint_matrix.keys()}
    events = list(events)

    for r in range(1, len(events) + 1):
        for subset in combinations(events, r):
            if is_independent_set(footprint_matrix, subset):
                independent_sets.append(set(subset))
    
    return independent_sets

def check_relationship(footprint_matrix, A, B):
    """
    Checks the relationship between two events or sets of events.
    
    Parameters:
        footprint_matrix (dict): Footprint matrix.
        A (str or set): Event or set of events.
        B (str or set): Event or set of events.

    Returns:
        str: Relationship if found, otherwise None.
    """
    if isinstance(A, str) and isinstance(B, str):
        return footprint_matrix.get((A, B))
    
    relationships = set()
    if isinstance(A, set) and isinstance(B, set):
        relationships.update(footprint_matrix.get((a, b)) for a in A for b in B)
    elif isinstance(A, set):
        relationships.update(footprint_matrix.get((a, B)) for a in A)
    elif isinstance(B, set):
        relationships.update(footprint_matrix.get((A, b)) for b in B)
    
    return relationships.pop() if len(relationships) == 1 else None

def find_transitions(footprint_matrix, independent_sets):
    """
    Finds transitions between independent sets.
    
    Parameters:
        footprint_matrix (dict): Footprint matrix.
        independent_sets (list): List of independent sets.

    Returns:
        dict: Transitions between independent sets.
    """
    transitions = {}
    for set1, set2 in combinations(independent_sets, 2):
        relationship = check_relationship(footprint_matrix, set1, set2)
        if relationship in ("-->", "| |"):
            transitions[(tuple(set1), tuple(set2))] = relationship
        elif relationship == "<--":
            transitions[(tuple(set2), tuple(set1))] = "-->"
    
    return transitions

def deconstruct_subset(subset):
    """
    Deconstructs a complex subset into all possible pairs of events.
    
    Parameters:
        subset (tuple): A complex subset represented as a tuple of frozensets.
        
    Returns:
        set: A set of pairs derived from the complex subset.
    """
    set1, set2 = subset
    return set(product(set1, set2))

def map_pairs_to_sets(transitions):
    """
    Maps pairs of events to larger sets they are part of.
    
    Parameters:
        transitions (dict): A dictionary of transitions with relationships between sets.
        
    Returns:
        dict: A dictionary where keys are pairs of events and values are sets of larger sets containing those pairs.
    """
    pair_to_sets = {}
    
    for complex_set in transitions.keys():
        pairs = deconstruct_subset(complex_set)
        if transitions.get(complex_set) == '| |':
            # Include the reverse direction for parallel relationships
            reverse_pairs = {(b, a) for a, b in pairs}
            pairs.update(reverse_pairs)
        for pair in pairs:
            if pair not in pair_to_sets:
                pair_to_sets[pair] = set()
            pair_to_sets[pair].add(complex_set)
    
    return pair_to_sets

def filter_maximal_sets(transitions):
    """
    Filters out non-maximal sets from the transitions dictionary.
    
    Parameters:
        transitions (dict): A dictionary of transitions with relationships between sets.
        
    Returns:
        dict: A dictionary with non-maximal sets removed.
    """
    pair_to_sets = map_pairs_to_sets(transitions)
    maximal_sets = set(transitions.keys())
    
    for complex_set in transitions.keys():
        pairs = deconstruct_subset(complex_set)
        for pair in pairs:
            for larger_set in pair_to_sets[pair]:
                if larger_set != complex_set and all(p in deconstruct_subset(larger_set) for p in pairs):
                    maximal_sets.discard(complex_set)
                    break
            if complex_set not in maximal_sets:
                break
        
    
    # Remove transitions that are not in the maximal sets
    return {complex_set: relationship for complex_set, relationship in transitions.items() if complex_set in maximal_sets}

def start_analyser():
    """
    Starts the analysis process.
    """
    try:
        log_file_name = param['tested_file']
        trace_dict = read_log_file(log_file_name)
        footprint_matrix = create_footprint(compute_directly_follows(trace_dict, *identify_initial_and_final_events(trace_dict)))
        independent_sets = find_independent_sets(footprint_matrix)
        transitions = find_transitions(footprint_matrix, independent_sets)
        maximal_sets = filter_maximal_sets(transitions)

        logging.info(f"Footprint Matrix: {footprint_matrix}")
        logging.info(f"Independent Sets: {independent_sets}")
        logging.info(f"Transitions: {transitions}")
        logging.info(f"Maximal Sets: {maximal_sets}")
    
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    start_analyser()
