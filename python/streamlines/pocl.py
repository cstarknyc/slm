"""
Prep PyOpenCL kernel
"""

import pyopencl as cl
import pyopencl.tools as cltools
import numpy as np
from os import environ
from streamlines import state
from streamlines.useful import vprint
import warnings

environ['PYOPENCL_COMPILER_OUTPUT']='0'

__all__ = ['prepare_cl_context','choose_platform_and_device',
           'prepare_cl_queue', 'prepare_cl',
           'make_cl_dtype',
           'set_compile_options', 
           'report_kernel_info', 'report_device_info', 'report_build_log',
           'adaptive_enqueue_nd_range_kernel',
           'prepare_buffers', 'gpu_compute']

pdebug = print

def prepare_cl_context(cl_platform=0, cl_device=2):
    """
    Prepare PyOpenCL platform, device and context.
    
    Args:
        cl_platform (int):
        cl_device (int):
    
    Returns:
        pyopencl.Platform, pyopencl.Device, pyopencl.Context:
            PyOpenCL platform, PyOpenCL device, PyOpenCL context
    """
    cl_platform, cl_device = choose_platform_and_device(cl_platform,cl_device)
    platform = cl.get_platforms()[cl_platform]
    devices = platform.get_devices()
    device = devices[cl_device]
    context = cl.Context([device])
    return platform, device, context

def choose_platform_and_device(cl_platform='env',cl_device='env'):
    """
    Get OpenCL platform & device from environment variables if they are set.
    
    Args:
        cl_platform (int):
        cl_device (int):
    
    Returns:
        int, int:
            CL platform, CL device
    """
    if cl_platform=='env':
        try:
            cl_platform = int(environ['PYOPENCL_CTX'].split(':')[0])
        except:
            cl_platform = 0
    if cl_device=='env':
        try:
            cl_device = int(environ['PYOPENCL_CTX'].split(':')[1])
        except:
            cl_device = 2
    return cl_platform, cl_device

def prepare_cl_queue(context=None, cl_kernel_source=None, compile_options=[]):
    """
    Build PyOpenCL program and prepare command queue.
    
    Args:
        context (pyopencl.Context): GPU/OpenCL device context
        cl_kernel_source (str): OpenCL kernel code string
    
    Returns:
        pyopencl.Program, pyopencl.CommandQueue: 
            PyOpenCL program, PyOpenCL command queue
    """
#     compile_options = ['-cl-fast-relaxed-math',
#                        '-cl-single-precision-constant',
#                        '-cl-unsafe-math-optimizations',
#                        '-cl-no-signed-zeros',
#                        '-cl-finite-math-only']
    program = cl.Program(context, cl_kernel_source).build(cache_dir=False,
                                                          options=compile_options)
    queue = cl.CommandQueue(context)
    return program, queue

def prepare_cl(cl_platform=0, cl_device=2, cl_kernel_source=None, compile_options=[]):
    """
    Prepare PyOpenCL stuff.
    
    Args:
        cl_device (int):
        cl_kernel_source (str): OpenCL kernel code string
    
    Returns:
        pyopencl.Platform, pyopencl.Device, pyopencl.Context, pyopencl.Program, \
        pyopencl.CommandQueue:
            PyOpenCL platform, PyOpenCL device, PyOpenCL context, PyOpenCL program, \
            PyOpenCL command queue
    """
    platform,device,context = prepare_cl_context(cl_platform,cl_device)
    program,queue = prepare_cl_queue(context,cl_kernel_source,compile_options)
    return platform, device, context, program, queue

def make_cl_dtype(device,name,dtype):
    """
    Generate an OpenCL structure typedef codelet from a numpy structured 
    array dtype.
    
    Currently unused.
    
    Args:
        cl_device (int):
        name (str):
        dtype (numpy.dtype):
    
    Returns:
        numpy.dtype, pyopencl.dtype, str: 
            processed dtype, cl dtype, CL typedef codelet
    """
    processed_dtype, c_decl = cltools.match_dtype_to_c_struct(device, name, dtype)
    return processed_dtype, cltools.get_or_register_dtype(name, processed_dtype), c_decl

def set_compile_options(info_dict, kernel_def, downup_sign=1,
                        job_type='integration'):
    """
    Convert the info struct into a list of '-D' compiler macros.
    
    Args:
        info_dict (numpy.ndarray): container for myriad parameters controlling
            trace() and mapping() workflow and corresponding GPU/OpenCL device operation
        kernel_def (str): name of the kernel in the program source string; 
            is used by #ifdef kernel-wrapper commands in the OpenCL codes
        downup_sign (bool): flag used to indicate desired sense of streamline integration,
               with +1 for downstream and -1 for upstream ['integration' mode]
        job_type (str): switch between 'integration' (default) and 'kde'
        
    Returns:
        list:
            compile options
    """
    if job_type=='kde':
        rtn_list = [
            '-D','KERNEL_{}'.format(kernel_def.upper()),
            '-D','KDF_BANDWIDTH={}f'.format(info_dict['kdf_bandwidth']),
            '-D','KDF_IS_{}'.format(info_dict['kdf_kernel'].upper()),
            '-D','N_DATA={}u'.format(info_dict['n_data']),
            '-D','N_HIST_BINS={}u'.format(info_dict['n_hist_bins']),
            '-D','N_PDF_POINTS={}u'.format(info_dict['n_pdf_points']),
            '-D','X_MIN={}f'.format(info_dict['x_min']),
            '-D','X_MAX={}f'.format(info_dict['x_max']),
            '-D','X_RANGE={}f'.format(info_dict['x_range']),
            '-D','BIN_DX={}f'.format(info_dict['bin_dx']),
            '-D','PDF_DX={}f'.format(info_dict['pdf_dx']),
            '-D','KDF_WIDTH_X={}f'.format(info_dict['kdf_width_x']),
            '-D','N_KDF_PART_POINTS_X={}u'.format(info_dict['n_kdf_part_points_x']),
            '-D','Y_MIN={}f'.format(info_dict['y_min']),
            '-D','Y_MAX={}f'.format(info_dict['y_max']),
            '-D','Y_RANGE={}f'.format(info_dict['y_range']),
            '-D','BIN_DY={}f'.format(info_dict['bin_dy']),
            '-D','PDF_DY={}f'.format(info_dict['pdf_dy']),
            '-D','KDF_WIDTH_Y={}f'.format(info_dict['kdf_width_y']),
            '-D','N_KDF_PART_POINTS_Y={}u'.format(info_dict['n_kdf_part_points_y'])
        ]
        if info_dict['debug']:
            rtn_list += ['-D', 'DEBUG']
        return rtn_list

    else:
        rtn_list = [
        '-D','KERNEL_{}'.format(kernel_def.upper()),
        '-D','N_SEED_POINTS={}u'.format(info_dict['n_seed_points']),
        '-D','DOWNUP_SIGN={}'.format(downup_sign),
        '-D','INTEGRATOR_STEP_FACTOR={}f'.format( 
                                            info_dict['integrator_step_factor']),
        '-D','MAX_INTEGRATION_STEP_ERROR={}f'.format(
                                info_dict['max_integration_step_error']),
        '-D','ADJUSTED_MAX_ERROR={}f'.format( info_dict['adjusted_max_error']),
        '-D','MAX_LENGTH={}f'.format(info_dict['max_length']),
        '-D','PIXEL_SIZE={}f'.format(info_dict['pixel_size']),
        '-D','INTEGRATION_HALT_THRESHOLD={}f'.format(
                                info_dict['integration_halt_threshold']),
        '-D','PAD_WIDTH={}u'.format(info_dict['pad_width']),
        '-D','PAD_WIDTH_PP5={}f'.format(info_dict['pad_width_pp5']),
        '-D','NX={}u'.format(info_dict['nx']),
        '-D','NY={}u'.format(info_dict['ny']),
        '-D','NXF={}f'.format(info_dict['nxf']),
        '-D','NYF={}f'.format(info_dict['nyf']),
        '-D','NX_PADDED={}u'.format(info_dict['nx_padded']),
        '-D','NY_PADDED={}u'.format(info_dict['ny_padded']),
        '-D','NXY_PADDED={}u'.format(info_dict['nxy_padded']),
        '-D','X_MAX={}f'.format(info_dict['x_max']),
        '-D','Y_MAX={}f'.format(info_dict['y_max']),
        '-D','GRID_SCALE={}f'.format(info_dict['grid_scale']),
        '-D','COMBO_FACTOR={}f'.format(info_dict['combo_factor']*downup_sign),
        '-D','DT_MAX={}f'.format(info_dict['dt_max']),
        '-D','MAX_N_STEPS={}u'.format(info_dict['max_n_steps']),
        '-D','TRAJECTORY_RESOLUTION={}u'.format(info_dict['trajectory_resolution']),
        '-D','SEEDS_CHUNK_OFFSET={}u'.format(info_dict['seeds_chunk_offset']),
        '-D','SUBPIXEL_SEED_POINT_DENSITY={}u'.format(
                                        info_dict['subpixel_seed_point_density']),
        '-D','SUBPIXEL_SEED_HALFSPAN={}f'.format(
                                        info_dict['subpixel_seed_halfspan']),
        '-D','SUBPIXEL_SEED_STEP={}f'.format(info_dict['subpixel_seed_step']),
        '-D','JITTER_MAGNITUDE={}f'.format(info_dict['jitter_magnitude']),
        '-D','INTERCHANNEL_MAX_N_STEPS={}u'.format(
                                             info_dict['interchannel_max_n_steps']),
        '-D','SEGMENTATION_THRESHOLD={}u'.format(
                                            info_dict['segmentation_threshold']),
        '-D','LEFT_FLANK_ADDITION={}u'.format(info_dict['left_flank_addition']),
        '-D','IS_CHANNEL={}u'.format(info_dict['is_channel']),
        '-D','IS_THINCHANNEL={}u'.format(info_dict['is_thinchannel']),
        '-D','IS_INTERCHANNEL={}u'.format(info_dict['is_interchannel']),
        '-D','IS_CHANNELHEAD={}u'.format(info_dict['is_channelhead']),
        '-D','IS_CHANNELTAIL={}u'.format(info_dict['is_channeltail']),
        '-D','IS_MAJORCONFLUENCE={}u'.format(info_dict['is_majorconfluence']),
        '-D','IS_MINORCONFLUENCE={}u'.format(info_dict['is_minorconfluence']),
        '-D','IS_MAJORINFLOW={}u'.format(info_dict['is_majorinflow']),
        '-D','IS_MINORINFLOW={}u'.format(info_dict['is_minorinflow']),
        '-D','IS_LEFTFLANK={}u'.format(info_dict['is_leftflank']),
        '-D','IS_RIGHTFLANK={}u'.format(info_dict['is_rightflank']),
        '-D','IS_MIDSLOPE={}u'.format(info_dict['is_midslope']),
        '-D','IS_RIDGE={}u'.format(info_dict['is_ridge']),
        '-D','WAS_CHANNELHEAD={}u'.format(info_dict['was_channelhead']),
        '-D','IS_LOOP={}u'.format(info_dict['is_loop']),
        '-D','IS_BLOCKAGE={}u'.format(info_dict['is_blockage'])
        ]
        if info_dict['debug']:
            rtn_list += ['-D', 'DEBUG']
        return rtn_list

def report_kernel_info(device,kernel,verbose):
    """
    Fetch and print GPU/OpenCL kernel info.
    
    Args:
        device (pyopencl.Device):
        kernel (pyopencl.Kernel):
        verbose (bool):
    """
    if verbose:
        # Report some GPU info
        print('Kernel reference count:',
              kernel.get_info(
                  cl.kernel_info.REFERENCE_COUNT))
        print('Kernel number of args:',
              kernel.get_info(
                  cl.kernel_info.NUM_ARGS))
        print('Kernel function name:',
              kernel.get_info(
                  cl.kernel_info.FUNCTION_NAME))
        print('Maximum work group size:',
              kernel.get_work_group_info(
                  cl.kernel_work_group_info.WORK_GROUP_SIZE, device))
        print('Recommended work group size:',
              kernel.get_work_group_info(
                  cl.kernel_work_group_info.PREFERRED_WORK_GROUP_SIZE_MULTIPLE, device))
        print('Local memory size:',
              kernel.get_work_group_info(
                  cl.kernel_work_group_info.LOCAL_MEM_SIZE, device), 'bytes')
        print('Private memory size:',
              kernel.get_work_group_info(
                  cl.kernel_work_group_info.PRIVATE_MEM_SIZE, device), 'bytes')    

def report_device_info(cl_platform, cl_device, platform, device, verbose):
    """
    Fetch and print GPU/OpenCL device info.
    
    Args:
        cl_platform (int):
        cl_device (int):
        platform (pyopencl.Platform):
        device (pyopencl.Device):
        verbose (bool):
    """
    if verbose:
        print('OpenCL platform #{0} = {1}'.format(cl_platform,platform))
        print('OpenCL device #{0} = {1}'.format(cl_device,device))
        n_bytes = device.get_info(cl.device_info.GLOBAL_MEM_SIZE)
        print('Global memory size: {} bytes = {}'.format(n_bytes,state.neatly(n_bytes)))
        n_bytes = device.get_info(cl.device_info.MAX_MEM_ALLOC_SIZE)
        print('Max memory alloc size: {} bytes = {}'
                            .format(n_bytes,state.neatly(n_bytes)))
        
        device_info_list = [s for s in dir(cl.device_info) if not s.startswith('__')]
        for s in device_info_list:
            try:
                print('{0} = {1}'.format(s,device.get_info(getattr(cl.device_info,s))))
            except:
                pass

def report_build_log(program, device, verbose):
    """
    Fetch and print GPU/OpenCL program build log.
    
    Args:
        program (pyopencl.Program):
        device (pyopencl.Device):
        verbose (bool):
    """
    build_log = program.get_build_info(device,cl.program_build_info.LOG)
    if len(build_log.replace(' ',''))>0:
        vprint(verbose,'\nOpenCL build log: {}'.format(build_log))
        
def adaptive_enqueue_nd_range_kernel(queue, kernel, global_size, local_size, 
                                     n_work_items, chunk_size_factor=10, 
                                     max_time_per_kernel=4.0, verbose=True):
    work_size  = n_work_items*int(np.ceil(global_size[0]/n_work_items))
    work_left  = work_size
    chunk_size = min(n_work_items*chunk_size_factor,work_left)
    offset = 0
    cumulative_time = 0.0
    time_per_item   = 0.0
    while work_left>0:
#         event = cl.enqueue_nd_range_kernel(queue, kernel, [chunk_size+offset,1], 
        event = cl.enqueue_nd_range_kernel(queue, kernel, [chunk_size,1], 
                                           local_size,global_work_offset=[offset,0])
        progress = 100.0*(min(work_size,(offset+chunk_size))/work_size)
        vprint(verbose,
               '{0:.2f}%: enqueued {1}/{2} workitems'
                    .format(progress,chunk_size,work_size),
                'in [{0}-{1}]'.format(offset,offset+chunk_size-1),
                'estimated t={0:.3f}s...'.format(time_per_item*chunk_size),
                end='')
        offset    += chunk_size
        work_left -= chunk_size
        event.wait()
        try:
            elapsed_time = 1e-9*(event.profile.end-event.profile.start)
            vprint(verbose, '...actual t={0:.3f}s'.format(elapsed_time))
        except:
            vprint(verbose, '...profiling failed')
            continue
        cumulative_time += elapsed_time
        time_per_item    = elapsed_time/chunk_size
        chunk_size = n_work_items*(min(
                            int(max_time_per_kernel/(time_per_item*n_work_items)),
                            int(np.ceil(work_left/n_work_items)) ))
    return cumulative_time

def prepare_buffers(context, array_dict, verbose):
    """
    Create PyOpenCL buffers and np-workalike arrays to allow CPU-GPU data transfer.
    
    Args:
        context (pyopencl.Context):
        array_dict (dict):
        verbose (bool):
        
    Returns:
        dict: buffer_dict
    """
    # Buffers to GPU memory
    COPY_READ_ONLY  = cl.mem_flags.READ_ONLY  | cl.mem_flags.COPY_HOST_PTR
    COPY_READ_WRITE = cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR
    WRITE_ONLY      = cl.mem_flags.WRITE_ONLY
    # The following could be packed into a list comprehension but would be
    #   rather harder to read in that form
    buffer_dict = {}
    for array_info in array_dict.items():
        if 'R' in array_info[1]['rwf']:
            if array_info[1]['rwf']=='RO':
                flags = COPY_READ_ONLY
            elif array_info[1]['rwf']=='RW':
                flags = COPY_READ_WRITE 
            buffer_dict.update({
                array_info[0]: cl.Buffer(context, flags, hostbuf=array_info[1]['array'])
            })
        elif array_info[1]['rwf']=='WO':
            flags = WRITE_ONLY
            pdebug(array_info[0],array_info[1]['array'].nbytes)
            buffer_dict.update({
                array_info[0]: cl.Buffer(context, flags, array_info[1]['array'].nbytes)
            })
        else:
            pass
    return buffer_dict

def gpu_compute(device,context,queue, cl_kernel_source,cl_kernel_fn, 
                info_dict, array_dict, verbose):
    """
    Carry out GPU computation.
    
    Args:
        device (pyopencl.Device):
        context (pyopencl.Context):
        queue (pyopencl.CommandQueue):
        cl_kernel_source (str):
        cl_kernel_fn (str):
        info_dict (dict):
        array_dict (dict):
        verbose (bool):  
        
    """
        
    # Prepare memory, buffers 
    buffer_dict = prepare_buffers(context, array_dict, verbose)    

    # Specify this integration job's parameters
    global_size         = [info_dict['n_seed_points'],1]
    n_work_items        = info_dict['n_work_items']
    local_size          = [n_work_items,1]
    chunk_size_factor   = info_dict['chunk_size_factor']
    max_time_per_kernel = info_dict['max_time_per_kernel']

    # Compile the CL code
    compile_options = set_compile_options(info_dict, cl_kernel_fn, downup_sign=1)
    vprint(verbose,'Compile options:\n', compile_options)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        program = cl.Program(context, cl_kernel_source).build(options=compile_options)
    report_build_log(program, device, verbose)
    # Set the GPU kernel
    kernel = getattr(program,cl_kernel_fn)
    # Designate buffered arrays
    kernel.set_args(*list(buffer_dict.values()))
    kernel.set_scalar_arg_dtypes( [None]*len(buffer_dict) )
    
    # Do the GPU compute
    vprint(verbose,
           '#### GPU/OpenCL computation: {0} work items... ####'.format(global_size[0]))
    report_kernel_info(device,kernel,verbose)
    elapsed_time \
        = adaptive_enqueue_nd_range_kernel( queue, kernel, global_size, 
                                            local_size, n_work_items,
                                            chunk_size_factor=chunk_size_factor,
                                            max_time_per_kernel=max_time_per_kernel,
                                            verbose=verbose )
    vprint(verbose,
           '#### ...elapsed time for {1} work items: {0:.3f}s ####'
           .format(elapsed_time,global_size[0]))
    queue.finish()   
    
    # Fetch the data back from the GPU and finish
    for array_info in array_dict.items():
        if 'W' in array_info[1]['rwf']:
            cl.enqueue_copy(queue, array_info[1]['array'], buffer_dict[array_info[0]])
            queue.finish()   
