#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This module contains the FSL-T1 pipeline."""

def t1_fsl_segmentation_pipeline(
                 datasink_directory, working_directory=None, is_bias_corrected=None,
                 name="t1_fsl_segmentation_pipeline"):
     """
     Perform segmentation of T1-weighted image by FSL.

     This pipeline performs all the FSL commands than can be performed on a
     T1-weighted image (BET for brain extraction, FAST for tissue segmentation,
     FIRST for gray nuclei segmentation).

     TODO - Connect the output of FAST to FIRST when T1 is not bias-corrected.

     Args:
         datasink_directory (str): Directory where the results are stored.
         working_directory (Optional[str]): Directory where the temporary
             results are stored. If not specified, it is automatically
             generated (generally in /tmp/).
         is_bias_corrected (boolean): Indicate if the image is bias-corrected
            or not.

     Inputnode:
         in_t1 (str): File containing the T1-weighted image.

     Outputnode:
         out_bet_binary_mask (str): File containing the binary image of the
            brain extracted image.
         out_brain_extracted (str): File containing the (bias-corrected) brain
            extracted image.
         out_bias_field (str): Estimated bias field. Present only if the input
            image is not bias-corrected.
         out_partial_volume_files: (list[str]): list of partial volume
            estimations for each tissue type (0=CSF, 1=GM, 2=WM)
         out_probability_maps: (a list of items which are a file name)
         out_tissue_class_files (list[str]): list of binary images for each
            tissue type (0=CSF, 1=GM, 2=WM)

     Example:
         >>> from clinica.pipeline.preprocessing.t1_fsl_pipeline import t1_fsl_segmentation_pipeline
         >>> fsl_segmentation = tractography_pipeline(datasink_directory='/path/to/datasink/directory', is_bias_corrected=True)
         >>> fsl_segmentation.inputs.inputnode.in_t1 = 'subject_bias_corrected_t1.nii'
         >>> fsl_segmentation.run()
     """
     import os
     import nipype.interfaces.fsl as fsl
     import nipype.interfaces.io as nio
     import nipype.interfaces.utility as niu
     import nipype.pipeline.engine as pe
     from os.path import join
     import tempfile
     from clinica.utils.mrtrix import dilate_mask
     from clinica.utils.fsl import standard_space_roi


     if working_directory is None:
         working_directory = tempfile.mkdtemp()

     try:
         fsl_dir = os.environ.get('FSLDIR', '')
         if not fsl_dir:
             raise RuntimeError('FSLDIR variable is not set')
     except Exception as e:
         print(str(e))
         exit(1)

     try:
         if fsl.Info.version().split(".") < ['5','0','5']:
             raise RuntimeError('FSL version must be greater than 5.0.5')
     except Exception as e:
         print(str(e))
         exit(1)

     inputnode = pe.Node(niu.IdentityInterface(fields=['in_t1']), name='inputnode')

     dilate_mask = pe.Node(interface=niu.Function(
         input_names=['in_mask', 'npass', 'nthreads'],
         output_names=['out_dilated_mask'],
         function=dilate_mask), name='dilate_mask')
     dilate_mask.inputs.in_mask = os.path.join(fsl_dir, 'data', 'standard', 'MNI152_T1_1mm_brain_mask_dil.nii.gz')

     standard_space_roi = pe.Node(interface=niu.Function(
         input_names=['in_t1', 'in_mask'],
         output_names=['out_pre_mask'],
         function=standard_space_roi), name='standard_space_roi')

     # The fractional intensity threshold is the one used by the MRtrix community
     fsl_bet = pe.Node(fsl.BET(frac=0.15, mask=True, robust=True), name='fsl_bet')

     if is_bias_corrected is None:
         raise RuntimeError('In t1_fsl_segmentation_pipeline: is_bias_corrected parameter is not set (it should be True of False)')
     elif is_bias_corrected:
         fsl_fast = pe.Node(fsl.FAST(out_basename='fast', img_type=1, number_classes=3, segments=True), name='fsl_fast')
     else:
         fsl_fast = pe.Node(fsl.FAST(out_basename='fast', img_type=1, number_classes=3,
            output_biascorrected=True, output_biasfield=True, segments=True), name='fsl_fast')

     fsl_first = pe.Node(fsl.FIRST(out_file='first', brain_extracted=True), name='fsl_fast')

     outputnode = pe.Node(niu.IdentityInterface(
         fields=['out_bet_binary_mask', 'out_brain_extracted']),
         name='outputnode')

     datasink = pe.Node(nio.DataSink(), name='datasink')
     datasink.inputs.base_directory = join(datasink_directory, 'fsl_t1_segmentation/')

     wf = pe.Workflow(name=name)
     wf.connect([
         # Pre-mask the T1-weighted image to standard space:
         (inputnode,   standard_space_roi, [('in_t1', 'in_t1')]),
         (dilate_mask, standard_space_roi, [('out_dilated_mask', 'in_mask')]),
         # Brain extraction of the T1-weighted image:
         (standard_space_roi, fsl_bet, [('out_pre_mask', 'in_file')]),
         # Segmentation of the different tissues:
         (fsl_bet, fsl_fast, [('out_file', 'in_files')]),
         # Segmentation of the sub-cortical structures: # TODO: Solve Bug - IndexError: list index out of range
#         (inputnode, fsl_first, [('in_t1', 'in_file')]),
         # Outputnode:
         (fsl_bet,  outputnode, [('mask_file', 'out_bet_binary_mask')]),
         # Saving files with datasink:
         (fsl_bet,   datasink, [('mask_file', 'out_bet_binary_mask')]),
         (fsl_fast,  datasink, [('partial_volume_files', 'out_partial_volume_files')]),
         (fsl_fast,  datasink, [('probability_maps', 'out_probability_maps')]),
         (fsl_fast,  datasink, [('tissue_class_files', 'out_tissue_class_files')]),
#         (fsl_fast,  datasink, [('mixeltype', 'out_mixeltype')]),
#         (fsl_first, datasink, [('bvars', 'out_bvars')]),
#         (fsl_first, datasink, [('original_segmentations', 'out_original_segmentations')]),
#         (fsl_first, datasink, [('segmentation_file', 'out_segmentation_file')]),
#         (fsl_first, datasink, [('vtk_surfaces', 'out_vtk_surfaces')])
     ])

     if is_bias_corrected:
         wf.connect([
            (fsl_bet, outputnode, [('out_file', 'out_brain_extracted')]),
            (fsl_bet, datasink, [('out_file', 'out_brain_extracted')])
         ])
     else:
         wf.connect([
            (fsl_fast, outputnode, [('restored_image', 'out_brain_extracted')]),
            (fsl_fast, datasink, [('restored_image', 'out_brain_extracted')]),
            (fsl_fast, datasink, [('bias_field', 'out_bias_field')])
         ])

     return wf