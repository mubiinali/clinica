from os import path
import logging
from glob import glob
import fileinput
from shutil import copy
import nibabel as nib

import os


def remove_rescan(list_path):
    """
    Remove all the folders containing the keyword 'rescan' from
    a given list of folders.

    Args:
        list_path (str): the list of the files to analize.

    Returns:
        The list of non rescanned folders.

    """
    # Extract all the folders without the substring 'rescan'
    no_resc_lst = [s for s in list_path if 'rescan' not in s]
    if len(no_resc_lst) != len(list_path):
        for r_file in list(set(list_path)-set(no_resc_lst)):
            logging.warning('Rescan found '+r_file+' Ignored.')

    return no_resc_lst


def choose_correction(dir, to_consider, mod):
    """
    Decides what is the best file type to choose depending on a priority list.

    The selection criteria is based on the input list toConsider that contains
    the files to consider in order of priority.

    Args:
        dir: the directory containing the files.
        to_consider: the list of files to consider in order of priority.
        mod: the modality

    Returns:
        The best file (according to the list to_consider) for the given modality or:
        -1 if if the modality is missing.
        0 if none of the desided corrections is available..

    """
    # extract all the files available for a certain modality
    correction_list = remove_rescan(glob(path.join(dir, '*' + mod + '*')))
    if len(correction_list) == 0:
        return -1
    if len(correction_list) == 1:
        return correction_list[0].split(os.sep)[-1]
    else:
        for i in range(0, len(to_consider)):
            if any(to_consider[i] in c for c in correction_list):
                return to_consider[i]
        return 0


def get_bids_suff(mod):
    """
    Returns the BIDS suffix for a certain modality.

    Args:
        mod: modality.
    Returns:
        The suffix used in the BIDS standard for a certain modality.
    """
    bids_suff = {
        'T1': '_T1w',
        'T2': '_T2w',
        'Flair': '_FLAIR',
        'SingleMapPh': '_phasediff',
        'MultiMapPh': '_phase',
        'Map': '_magnitude',
        'fMRI': '_bold',
        'dwi': '_dwi'
    }

    return bids_suff[mod]


def convert_T1(t1_path, output_path, t1_bids_name):
    """
    Convert into the BIDS specification a T1 image.

    Args:
        t1_path: the path of the T1 images to convert.
        output_path: output folder path.
        t1_bids_name: name to give to the file.

    """
    if not os.path.exists(output_path):
        os.mkdir(output_path)
    copy(t1_path, path.join(output_path, t1_bids_name + get_bids_suff('T1') + '.nii.gz'))


def convert_fieldmap(folder_input, folder_output, name, fixed_file=[False,False]):
    """
    Extracts and converts into the BIDS specification fieldmap data.

    Args:
        folder_input: folder containing the fieldmap data.
        folder_output: folder where store the converted files.
        name: name of converted file.
        files_to_skip:

    Returns:
         -1 if the modality is not available.
         0 if the magnitude or the phase is missing (information incomplete).
    """

    mag_missing = map_ph_missing = False

    # Check if there is a map or mapPh fixed to convert
    if fixed_file[0] is False and fixed_file[1] is False:
        map = remove_rescan(glob(path.join(folder_input, "*MAP_*",'*.nii.gz')))
        map_ph = remove_rescan(glob(path.join(folder_input, "*MAPph_*", '*.nii.gz')))
    elif fixed_file[0] is False and fixed_file[1] is not False:
        map = remove_rescan(glob(path.join(folder_input, "*MAP_*",'*.nii.gz')))
        map_ph = glob(path.join(folder_input, fixed_file[1], '*.nii.gz'))
    elif fixed_file[0] is not False and fixed_file[1] is False:
        map = glob(path.join(folder_input, fixed_file[0], '*.nii.gz'))
        map_ph = remove_rescan(glob(path.join(folder_input, "*MAPph_*", '*.nii.gz')))
    else:
        map = glob(path.join(folder_input, fixed_file[0], '*.nii.gz'))
        map_ph = glob(path.join(folder_input, fixed_file[1], '*.nii.gz'))

    files_to_skip = ["13001PBA20150623M18B0MAPph_S016.nii.gz", "13002PRJ20150922M18B0MAPph_S014.nii.gz",
                    "11001PGM20130704M00B0MAPph_S010.bval","07002PPP20150116M18B0MAPph_S009.nii.gz",
                    "07003PGM20141217M18B0MAPph_S010.nii.gz"]
    if len(map) == 0:
        mag_missing = True
    if len(map_ph) == 0:
        map_ph_missing = True
    # If the information regarding the Fieldmap data are complete
    if len(map) > 0 and len(map_ph) > 0:
        map_ph_name = map_ph[0].split(os.sep)[-1]
        map_name = map[0].split(os.sep)[-1]

        # toSolve: there are some files that produce an error when loaded with Nibabel
        if (map_ph_name not in files_to_skip) and (map_name not in files_to_skip):
            # Open the files with Nibabel
            map_nib = nib.load(map[0])
            map_ph_nib = nib.load(map_ph[0])
            dim_map = (map_nib.header['dim'])[4]
            dim_map_ph = (map_ph_nib.header['dim'])[4]
            os.mkdir(path.join(folder_output))
            # Case 1: one phase difference image and at least one magnitude image
            if dim_map_ph == 1 and dim_map > 0:
                copy(map_ph[0], path.join(folder_output, name + get_bids_suff('SingleMapPh') + '.nii.gz'))
                os.system('fslsplit ' + map[0] + ' ' + path.join(folder_output, name + get_bids_suff('Map')))
                mag_list = glob(path.join(folder_output,name+get_bids_suff('Map')+'*'))

                for i in range(0, len(mag_list)):
                    old_mag_name = mag_list[i].split(os.sep)[-1]
                    # Remove the extension and the number sequence of fslsplit
                    new_mag_name = old_mag_name[:-11] + str(i+1)
                    os.rename(mag_list[i], path.join(folder_output, new_mag_name + ".nii.gz"))
            # Case 2: two phase images and two magnitude images'
            elif dim_map_ph == 2 and dim_map == 2:
                bids_name_ph = name + get_bids_suff('MultiMapPh')
                bids_name_mag = name + get_bids_suff('Map')
                os.system('fslsplit ' + map_ph[0] + ' ' + path.join(folder_output, bids_name_ph))
                os.system('fslsplit ' + map[0] + ' ' + path.join(folder_output, bids_name_mag))
                # Fslsplit produces files with a name not comply with BIDS specification, a rename is needed
                os.rename(path.join(folder_output, bids_name_mag + '0000.nii.gz'),
                          path.join(folder_output, bids_name_mag+'1.nii.gz'))
                os.rename(path.join(folder_output, bids_name_mag + '0001.nii.gz'),
                          path.join(folder_output, bids_name_mag + '2.nii.gz'))
                os.rename(path.join(folder_output, bids_name_ph + '0000.nii.gz'),
                      path.join(folder_output, bids_name_ph + '1.nii.gz'))
                os.rename(path.join(folder_output, bids_name_ph + '0001.nii.gz'),
                      path.join(folder_output, bids_name_ph + '2.nii.gz'))
    # The modalities is missing or incomplete
    else:
        if mag_missing == True and  map_ph_missing == True:
            return -1
        else:
            return 0


def convert_flair(folder_input, folder_output, name, fixed_file = False):
    """
    Extracts and converts T2Flair data.

    Args:
        folder_input: folder containing T2Flair.
        folder_output: output folder path.
        name: name to give to the output file.

    Returns:
        -1 if no T2FLAIR is found in the input folder.
    """
    # If a given T2FLAIR is given for the conversion use it
    if fixed_file!=False:
        fixed_flair_path = glob(path.join(folder_input,fixed_file,'*'))[0]
        copy(fixed_flair_path, path.join(folder_output, name + (get_bids_suff('Flair')) + '.nii.gz'))
    else:
        list_path = glob(path.join(folder_input,'*T2FLAIR*'))
        flair_lst = remove_rescan(list_path)
        if len(flair_lst) == 1:
            if not os.path.exists(folder_output):
                os.mkdir(folder_output)
            flair_path = glob(path.join(flair_lst[0], '*.nii.gz*'))[0]
            copy(flair_path, path.join(folder_output, name + (get_bids_suff('Flair')) + '.nii.gz'))
        elif len(flair_lst) == 0:
                return -1
        elif len(flair_lst)>1:
                logging.warning('Multiple FLAIR found, computation aborted.')
                raise


def convert_fmri(folder_input, folder_output, name, fixed_fmri=False):
    """
    Extracts and converts into the BIDS specification fmri data.

    Args:
        folder_input: the folder containing the fmri to convert.
        folder_output: the output folder.
        name:

    Returns:
        -1 if no fMRI file is found in the input folder.
    """
    if fixed_fmri is not False:
        fmri_lst = glob(path.join(folder_input, fixed_fmri))
    else:
        fmri_lst = remove_rescan(glob(path.join(folder_input, '*fMRI*')))
    if len(fmri_lst) > 0:
        if not os.path.exists(folder_output):
            os.mkdir(folder_output)
        fmri_file_path = glob(path.join(fmri_lst[0], '*.nii*'))[0]
        copy(fmri_file_path, path.join(folder_output, name + '_task-rest' + get_bids_suff('fMRI') + '.nii.gz'))
    else:
        logging.info('Non fMRI found for ' + folder_input)
        return -1


def merge_DTI(folder_input, folder_output, name, fixed_dti_list=False):
    """
    Merge all the DTI files of a given subject.

    For the merging only DTI folders containing all .nii.gz, .bval and .bvec are considered,
    otherwise the folder is ignored.

    Args:
        folder_input (str) : the folder containing all the DTI to merge.
        folder_output (str) : the folder where store the merged file.
        name (str): name to give to the merged file.

    Returns:
        -1 if the input folder doesn't contain any DTI folder.
        The list of incomplete DTI folders if there is some folders without bvec/bval/nii
    """
    img = []
    bval = []
    bvec = []
    dti_list = []

    if fixed_dti_list is not False:
        for dti in fixed_dti_list:
            dti_list.append(path.join(folder_input, dti))
    else:
        dti_list = remove_rescan(glob(path.join(folder_input, '*DTI*')))
    incomp_folders = []
    nr_dti = len(dti_list)
    if nr_dti == 0:
        return -1
    else:
        if not os.path.exists(folder_output):
            os.mkdir(folder_output)
        for folder in dti_list:
            if len(glob(path.join(folder, '*.bval'))) != 0 and len(glob(path.join(folder, '*.bvec'))) != 0:
                img.append(glob(path.join(folder,'*.nii*'))[0])
                bval.append(glob(path.join(folder,'*.bval'))[0])
                bvec.append(glob(path.join(folder,'*.bvec'))[0])
            else:
                incomp_folders.append(folder)

        # if it has been found at least a DTI folder complete with bvec, bval and nii.gz
        if len(img) > 0:
            file_suff = get_bids_suff('dwi')
            fin = fileinput.input(bval)
            # merge all the .nii.gz file with fslmerge
            os.system('fslmerge -t ' + path.join(folder_output, name + file_suff + '.nii.gz') + ' ' + " ".join(img))
            # merge all the .bval files
            fout = open(path.join(folder_output,name+file_suff+'.bval'), 'w')
            for line in fin:
                fout.write(line)
            #merge all the .bvec files
            fin = fileinput.input(bvec)
            fout = open(path.join(folder_output, name + file_suff + '.bvec'), 'w')
            for line in fin:
                fout.write(line)

        if len(incomp_folders) > 0:
            return incomp_folders