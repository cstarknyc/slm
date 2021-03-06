"""
---------------------------------------------------------------------

Wrapper module to locate channel heads using `OpenCL`_.

Requires `PyOpenCL`_.

Imports streamlines module :doc:`pocl`.
Imports functions from streamlines module :doc:`useful`.

---------------------------------------------------------------------


.. _OpenCL: https://www.khronos.org/opencl
.. _PyOpenCL: https://documen.tician.de/pyopencl/index.html

"""

import pyopencl as cl
import pyopencl.array
import numpy as np
import os
os.environ['PYTHONUNBUFFERED']='True'
import warnings

from streamlines import pocl
from streamlines.useful import vprint, pick_seeds, check_sizes

__all__ = ['map_channel_heads','prune_channel_heads']

pdebug = print

def map_channel_heads(cl_state, info, data, verbose):
    """
    Args:
        cl_state (obj):
        info (obj):
        data (obj):
        verbose (bool):

    Find channel head pixels.
    
    Returns:
        bool: flag false if failure occurs because seed points list is empty
    
    """
    vprint(verbose,'Mapping channel heads...')
    # Prepare CL essentials
    cl_state.kernel_source \
        = pocl.read_kernel_source(cl_state.src_path,['essentials.cl','updatetraj.cl',
                                                     'computestep.cl','rungekutta.cl',
                                                     'channelheads.cl'])

    # Pre-designate every channel pixel as a channel head
    #   - and expect to eliminate all non-heads during the GPU compute
    data.mapping_array[(data.mapping_array&info.is_thinchannel)==info.is_thinchannel] \
                            |= info.is_channelhead
        
    # Trace downstream from all non-masked pixels
    seed_point_array = pick_seeds(mask=data.mask_array, flag=info.is_channel, 
                                  pad=info.pad_width)
    # Specify arrays & CL buffers 
    array_dict = { 'seed_point':  {'array': seed_point_array,      'rwf': 'RO'},
                   'mask':        {'array': data.mask_array,       'rwf': 'RO'}, 
                   'uv':          {'array': data.uv_array,         'rwf': 'RO'}, 
                   'mapping':     {'array': data.mapping_array,    'rwf': 'RW'} }
    info.n_seed_points = seed_point_array.shape[0]
    if ( info.n_seed_points==0 ):
        # Flag an error - empty seeds list
        return False
    check_sizes(info.nx_padded,info.ny_padded, array_dict)
#     pdebug('map_channel_heads seed_point_array:',seed_point_array.shape)
    # Do integrations on the GPU
    cl_state.kernel_fn = 'map_channel_heads'
    pocl.gpu_compute(cl_state, info, array_dict, info.verbose)
    
    # Done
    vprint(verbose,'...done')  
    # Flag all went well
    return True

def prune_channel_heads(cl_state, info, data, verbose):
    """
    Args:
        cl_state (obj):
        info (obj):
        data (obj):
        verbose (bool):

    Prune channel head pixels.
    

    """
    vprint(verbose,'Pruning channel heads...')
    # Prepare CL essentials
    cl_state.kernel_source \
        = pocl.read_kernel_source(cl_state.src_path,['essentials.cl','updatetraj.cl',
                                                     'computestep.cl','rungekutta.cl',
                                                     'channelheads.cl'])

    # Eliminate all provisional channel heads that have >1 thin channel nbr        
    # Trace downstream from all non-masked pixels
    seed_point_array = pick_seeds(mask=data.mask_array, map=data.mapping_array, 
                                  flag=info.is_channelhead, pad=info.pad_width)
    # Specify arrays & CL buffers 
    array_dict = { 'seed_point':  {'array': seed_point_array,      'rwf': 'RO'},
                   'mask':        {'array': data.mask_array,       'rwf': 'RO'}, 
                   'uv':          {'array': data.uv_array,         'rwf': 'RO'}, 
                   'mapping':     {'array': data.mapping_array,    'rwf': 'RW'} }
    info.n_seed_points = seed_point_array.shape[0]
    check_sizes(info.nx_padded,info.ny_padded, array_dict)
#     pdebug('prune_channel_heads seed_point_array:',seed_point_array)
    # Do integrations on the GPU
    cl_state.kernel_fn = 'prune_channel_heads'
    pocl.gpu_compute(cl_state, info, array_dict, info.verbose)
    
    # Done
    vprint(verbose,'...done')
