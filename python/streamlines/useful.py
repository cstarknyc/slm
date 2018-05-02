"""
Miscellaneous useful functions for PyOpenCL code
"""

import numpy as np
import pandas as pd
import os
os.environ['PYTHONUNBUFFERED']='True'
import sys

__all__ = ['vprint','create_seeds','pick_seeds','compute_stats']

pdebug = print

def vprint(verbose, *args, **kwargs):
    """
    Wrapper for print() with verbose flag to suppress output if desired
    
    Args:
        verbose  (bool): turn printing on or off
        *args (str): print() function args
        **kwargs (str): print() function keyword args
    """
    if verbose:
        print(*args, **kwargs, flush=True)
        # Try to really force this line to print before the GPU prints anything
        sys.stdout.flush()

def create_seeds(mask, pad_width, n_work_items, n_seed_points=None,
                 do_shuffle=True, rng_seed=1, verbose=False):
    """
    Generate seed points for tracing of streamline trajectories.   
        
    Returns:
        numpy.ndarray: seed point array   
        int: n_seed_points  
        int: n_padded_seed_points  
    """    
    vprint(verbose,'Generating seed points...', end='')
    seed_point_array \
        = ((np.argwhere(~mask).astype(np.float32) - pad_width)
           ).copy()
    # Randomize seed point sequence to help space out memory accesses by kernel instances
    if do_shuffle:
        vprint(verbose,'shuffling...', end='')
        np.random.seed(rng_seed)
        np.random.shuffle(seed_point_array)
    # Truncate if we only want to visualize a subset of streamlines across the DTM
    if n_seed_points is not None:
        seed_point_array = seed_point_array[:n_seed_points].copy().astype(np.float32)
    else:
        n_seed_points = seed_point_array.shape[0]

    pad_length = (np.uint32(np.round(
                    n_seed_points/n_work_items+0.5))*n_work_items-n_seed_points)
    n_padded_seed_points = n_seed_points+pad_length
    if pad_length>0:
        vprint(verbose,'padding for {0} CL work items/group: {1}->{2}...'
                .format(n_work_items, n_seed_points,n_padded_seed_points ), end='')
    else:
        vprint(verbose,'no padding needed...', end='')
    vprint(verbose,'done')
    return seed_point_array, n_seed_points, n_padded_seed_points

def pick_seeds(mask=None, map=None, flag=None, pad=None):
    """
    Generate a vector array of seed points to send to the GPU/OpenCl device
    
    Args:
        mask (numpy.ndarray): pixel mask array
        map (numpy.ndarray):  mapping array (as generated by mapping())
        flag (bool): binary flag ORed with mapping array to pick seed pixels
        pad (int): grid boundary padding with in pixels
    
    Returns:
        numpy.ndarray: seed point array
    """
    if mask is None and map is not None:
        seed_point_array \
            = (np.argwhere(map & flag).astype(np.float32)-pad).copy()
    elif mask is not None and map is None:
        seed_point_array = (np.argwhere(~mask).astype(np.float32)-pad).copy()
    else:
        seed_point_array \
            = (np.argwhere(~mask & ((map & flag)>0)).astype(np.float32)-pad).copy()
    return seed_point_array
    
def compute_stats(traj_length_array, traj_nsteps_array, pixel_size, verbose):
    """
    Compute streamline integration point spacing and trajectory length statistics 
    (min, mean, max) for the sets of both downstream and upstream trajectories.
    Return them as a small Pandas dataframe table.
    
    Args:
        traj_length_array (numpy.ndarray):
        traj_nsteps_array (numpy.ndarray):
        pixel_size (float):
        verbose (bool):
        
    Returns:
        pandas.DataFrame:  lnds_stats_df
    """
    vprint(verbose,'Computing streamlines statistics')
    lnds_stats = []
    for downup_idx in [0,1]:
        lnds = np.array( [ [ln[0],ln[1],ln[0]/ln[1]] 
                            for ln in (np.stack(
                                 (traj_length_array[:,downup_idx]*pixel_size, 
                                            traj_nsteps_array[:,downup_idx])   ).T) ] )
        lnds_stats += [np.min(lnds,axis=0), np.mean(lnds,axis=0), np.max(lnds,axis=0)]
    lnds_stats_array = np.array(lnds_stats,dtype=np.float32)
    lnds_indexes = [np.array(['downstream', 'downstream', 'downstream', 
                              'upstream', 'upstream', 'upstream']),
                         np.array(['min','mean','max','min','mean','max'])]
    lnds_stats_df = pd.DataFrame(data=lnds_stats_array, 
                                 columns=['l','n','ds'],
                                 index=lnds_indexes)
    vprint(verbose,lnds_stats_df.T)
    return lnds_stats_df
