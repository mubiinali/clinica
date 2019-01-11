
__author__ = "Arnaud Marcoux"
__copyright__ = "Copyright 2016-2018 The Aramis Lab Team"
__credits__ = ["Arnaud Marcoux"]
__license__ = "See LICENSE.txt file"
__version__ = "0.2.0"
__maintainer__ = "Arnaud Marcoux"
__email__ = "arnaud.marcoux@inria.fr"
__status__ = "Development"


def likeliness_measure(file1, file2, threshold1, threshold2, display=False):
    """
        Function that compares 2 Nifti inputs, with 2 different thresholds.

        Args:
            (string) file1: path to first nifti input
            (string) file2: path to second nifti to compare
            (tuple) threshold1: defines the first criteria to meet: threshold1[0] defines the relative
                                difference between 2 voxels to be considered different (ex: 1e-4). threshold[1] defines
                                the maximum proportion of voxels that can different for the test to be negative.
            (tuple) threshold2: defines the second criteria to meet.
            (bool) display: If set to True, will display a useful graph to determine optimal threshold for the
                            comparison

        Returns:
            (bool) True if file1 and file2 can be considered similar enough (meeting criterion expressed in threshold1
                   and threshold2). False otherwise.

    """
    import nibabel as nib
    import numpy as np
    import os
    import matplotlib.pyplot as plt

    print(' ** comparing ' + os.path.basename(file1) + ' **')
    data1 = nib.load(file1).get_data()
    data1[data1 != data1] = 0

    data2 = nib.load(file2).get_data()
    data2[data2 != data2] = 0

    # Get mask where data are 0 in data1 and data2
    mask = (data1 == 0) & (data2 == 0)
    data1[mask] = 1
    data2[mask] = 1
    metric = (2 * np.abs(data1 - data2)) / (np.abs(data1) + np.abs(data2))
    metric_flattened = np.ndarray.flatten(metric)

    # Display fig
    if display:
        thresholds = np.logspace(-8, 0, 20)
        percents = np.array([np.sum((metric_flattened > T)) / metric_flattened.size for T in thresholds])
        fig, ax = plt.subplots()
        ax.semilogx(thresholds, percents)
        ax.grid()
        plt.xlabel('Threshold of relative difference')
        plt.ylabel('Proportion of different voxels')
        plt.show()

    mask_different_voxels_cond1 = metric_flattened > threshold1[0]
    mask_different_voxels_cond2 = metric_flattened > threshold2[0]
    return (np.sum(mask_different_voxels_cond1) / metric_flattened.size < threshold1[1]) & \
           (np.sum(mask_different_voxels_cond2) / metric_flattened.size < threshold2[1])


def similarity_measure(file1, file2, threshold):
    """
        Function that compares 2 Nifti inputs using a correlation metric. Nifti are equals if correlation gives

        Args:
            (string) file1: path to first nifti input
            (string) file2: path to second nifti to compare
            (float) threshold

        Returns:
            (bool) True if file1 and file2 can be considered similar enough. (superior than threshold)

    """
    import numpy as np
    import nipype.pipeline.engine as npe
    from nipype.algorithms.metrics import Similarity

    # Node similarity (nipy required)
    img_similarity = npe.Node(name='img_similarity',
                              interface=Similarity())
    img_similarity.inputs.metric = 'cc'  # stands for correlation coefficient
    img_similarity.inputs.volume1 = file1
    img_similarity.inputs.volume2 = file2
    res = img_similarity.run()

    return np.mean(res.outputs.similarity) > threshold


def identical_subject_list(sub_ses_list1, sub_ses_list2):
    """
        Function that ensures that both subject_session files are describing the same list

        Args:
            (string) sub_ses_list1: path to first nifti input
            (string) sub_ses_list2: path to second nifti to compare

        Returns:
            (bool) True if sub_ses_list1 and sub_ses_list2 contains the same sessions

    """
    def is_included(list1, list2):
        from pandas import read_csv

        # Read csv files
        readlist1 = read_csv(list1, sep='\t')
        readlist2 = read_csv(list2, sep='\t')

        # If columns are different, files are different
        if list(readlist1.columns) != list(readlist2.columns):
            return False
        else:

            # Extract subject and corresponding session names
            subjects1 = list(readlist1.participant_id)
            sessions1 = list(readlist1.session_id)
            subjects2 = list(readlist2.participant_id)
            sessions2 = list(readlist2.session_id)

            if len(subjects1) != len(subjects2):
                return False
            else:
                for i in range(len(subjects1)):
                    current_sub = subjects1[i]
                    current_ses = sessions1[i]
                    # Compute all the indices in the second list corresponding to the current subject
                    idx_same_sub = [j for j in range(len(subjects2)) if subjects2[j] == current_sub]
                    if len(idx_same_sub) == 0:  # Current subject not found in
                        return False
                    ses_same_sub = [sessions2[idx] for idx in idx_same_sub]
                    if current_ses not in ses_same_sub:
                        return False
        return True
    # The operation is performed both sides because is_included(list1, list2) != is_included(list2, list1)
    return is_included(sub_ses_list1, sub_ses_list2) & is_included(sub_ses_list2, sub_ses_list1)


def same_missing_modality_tsv(file1, file2):
    """
        Function that is used to compare 2 tsv generated by the iotool ComputeMissingModalities.

        Only fields participant_id, pet, t1w, func_task - rest are compared. Line order does not matter.


        Args:
            (string) file1: path to first tsv
            (string) file2: path to second tsv

        Returns:
            (bool) True if file1 and file2 contains the same informations

    """
    import pandas as pds

    # Read dataframe with pandas
    df1 = pds.read_csv(file1, sep='\t')
    df2 = pds.read_csv(file2, sep='\t')

    # Extract data and form lists for both files
    subjects1 = list(df1.participant_id)
    pet1 = list(df1.pet)
    t1w1 = list(df1.t1w)
    func_task_rest1 = list(df1['func_task-rest'])

    subjects2 = list(df2.participant_id)
    pet2 = list(df2.pet)
    t1w2 = list(df2.t1w)
    func_task_rest2 = list(df2['func_task-rest'])

    # Subjects are sorted in alphabetical order. The same permutation of element is applied on each column
    subjects1_sorted, pet1 = (list(t) for t in zip(*sorted(zip(subjects1, pet1))))
    subjects2_sorted, pet2 = (list(t) for t in zip(*sorted(zip(subjects2, pet2))))
    subjects1_sorted, t1w1 = (list(t) for t in zip(*sorted(zip(subjects1, t1w1))))
    subjects2_sorted, t1w2 = (list(t) for t in zip(*sorted(zip(subjects2, t1w2))))
    subjects1_sorted, func_task_rest1 = (list(t) for t in zip(*sorted(zip(subjects1, func_task_rest1))))
    subjects2_sorted, func_task_rest2 = (list(t) for t in zip(*sorted(zip(subjects2, func_task_rest2))))

    # Test is positive when all the sorted list s are equals
    return (subjects1_sorted == subjects2_sorted) & (pet1 == pet2) \
           & (t1w1 == t1w2) & (func_task_rest1 == func_task_rest2)
