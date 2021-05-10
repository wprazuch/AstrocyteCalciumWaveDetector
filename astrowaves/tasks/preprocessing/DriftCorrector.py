import fire
import numpy as np
from tqdm import tqdm
from sklearn.cluster import KMeans
from astrowaves.metrics import mse_loss
from pathlib import Path
import os
from tiffile import imread as tiff_read
from tiffile import imsave as tiff_save
from astrowaves.utils import generate_video
import pandas as pd

from scipy.fft import fft, ifft


def correct_drift(
    array_3d: np.array, method: str = "subregion", window_size: int = 100
) -> np.array:
    """Main function for drift correction. Meant for extension for various methods

    Parameters
    ----------
    array_3d : np.ndarray
        Input timelapse
    method : str, optional
        method of drift correction, by default "subregion"
    window_size : int, optional
        window size for subregion drift correction, by default 100

    Returns
    -------
    np.ndarray
        Motion corrected timelapse

    Raises
    ------
    AttributeError
        When timelapse fails
    """

    if method == "subregion":
        img_corrected = correct_by_subregion(array_3d, window_size=window_size)
    else:
        raise AttributeError(f"Method {method} not implemented!")

    return img_corrected


def find_best_subregion(array_3d, window_size=100, margin=50):
    no_windows = int((min(*array_3d.shape[1:]) - 2 * (margin)) / window_size)

    lowest_std = 0

    stds_list = []

    for i in range(1, no_windows - 1, 1):

        start_idx = i * window_size + margin
        end_idx = (i + 1) * window_size + margin

        for j in range(1, no_windows - 1, 1):

            start_idy = j * window_size + margin
            end_idy = (j + 1) * window_size + margin

            region = array_3d[:, start_idx:end_idx, start_idy:end_idy]

            key_ = (start_idx, start_idy)
            total_std = np.std(region)
            avg = np.mean(region)
            std_value_ = total_std

            stds_list.append((key_, std_value_, avg))

            if total_std > lowest_std:
                lowest_std = total_std

    stds = [item[1] for item in stds_list]

    kmeans = KMeans(n_clusters=2).fit(np.array(stds)[:, np.newaxis])
    labels = kmeans.labels_

    background_label = labels[np.argmin(stds)]
    idxs = np.argwhere(labels == background_label).squeeze().tolist()
    stds_background = [stds_list[i] for i in idxs]

    reference_region = max(stds_background, key=lambda x: x[2])[0]

    return reference_region


def correct_by_subregion(array_3d, window_size=100, margin=50):

    reference_region = find_best_subregion(
        array_3d.copy(), window_size=window_size, margin=margin
    )

    search_range = window_size + margin

    search_space = list(range(-search_range, search_range - 1, 1))

    shifts = []
    img_new = array_3d.copy()
    metric = mse_loss

    for k in tqdm(range(img_new.shape[0])):

        min_mse = 1000000000
        reference = img_new[0].copy()
        correcting = img_new[k].copy()

        reference = reference[
            reference_region[0] : reference_region[0] + window_size,
            reference_region[1] : reference_region[1] + window_size,
        ].copy()

        for i in search_space:

            start_x = reference_region[0] + i
            end_x = reference_region[0] + window_size + i

            for j in search_space:

                start_y = reference_region[1] + j
                end_y = reference_region[1] + window_size + j

                current = correcting[start_x:end_x, start_y:end_y].copy()

                mse = metric(current, reference)

                if mse < min_mse:
                    optimal_shift = (i, j)
                    min_mse = mse

        shifts.append(optimal_shift)

        slice_ = img_new[k, :, :].copy()
        shifted_slice = np.roll(slice_, -optimal_shift[0], axis=0)
        shifted_slice = np.roll(shifted_slice, -optimal_shift[1], axis=1)
        img_new[k, :, :] = shifted_slice

    return img_new


def perform_drift_correction(
    input_filepath, output_filepath=None, window_size=100, debug=True
):

    if output_filepath is None:
        filepath = Path(input_filepath)
        parent = filepath.parent
        suffix = filepath.suffix
        stem = filepath.stem

        output_filepath = os.path.join(parent, stem + "_corrected" + suffix)

    array_3d = tiff_read(input_filepath)
    array_3d = array_3d[100:400]

    array_3d_corrected = correct_drift(array_3d, window_size=window_size)

    tiff_save(output_filepath, array_3d_corrected, photometric="minisblack")

    if debug == True:
        generate_video(array_3d, parent, "original.mp4")
        generate_video(array_3d_corrected, parent, "drift_corrected.mp4")


def find_minimum(current_segment, reference_segment):

    current_idxs = np.argsort(current_segment)
    reference_idxs = np.argsort(reference_segment)

    for i in range(len(current_segment // 20)):
        for j in range(len(reference_segment // 20)):
            if current_idxs[i] == reference_idxs[j]:
                return current_idxs[i]

    return current_idxs[0]


def fft_correlation(spectrum, target, shift):
    M = len(target)
    diff = 1000000000
    for i in range(20 - 1):
        cur_diff = 2 ** i - M
        if cur_diff > 0 and cur_diff < diff:
            diff = cur_diff

    # changed by adding + 1 - CAUTION
    padding = np.zeros(diff)
    target = np.hstack([target, padding])
    spectrum = np.hstack([spectrum, padding])

    M = M + diff
    X = fft(target)
    Y = fft(spectrum)

    R = X * np.conj(Y)
    R = R / M
    rev = ifft(R)

    vals = np.real(rev)
    max_position = 0
    maxi = -1

    if M < shift:
        shift = M

    for i in range(shift):
        if vals[i] > maxi:
            maxi = vals[i]
            max_position = i

        if vals[len(vals) - i] > maxi:
            maxi = vals[len(vals) - i]
            max_position = len(vals) - i

    if maxi < 0.1:
        lag = 0
        return lag

    # CHANGED BY DELETING - 1 - CAUTION
    if max_position > len(vals) / 2:
        lag = max_position - len(vals)
    else:
        lag = max_position

    return lag


def move(seg, lag):
    if lag == 0 or lag >= len(seg):
        return seg

    if lag > 0:
        ins = [1 * seg[0] for item in range(lag)]
        moved_seg = [*ins, *seg[: len(seg) - lag]]
    elif lag < 0:
        lag = np.abs(lag)
        ins = [1 * seg[-1] for item in range(lag)]
        moved_seg = [*seg[lag:], *ins]

    return moved_seg


def pafft_motion_correction(img):

    df = pd.DataFrame()

    for i in tqdm(range(img.shape[0])):
        uniq, cnts = np.unique(img[i], return_counts=True)
        row_dict = dict(zip(uniq, cnts))
        df = df.append(row_dict, ignore_index=True)

    pixel_values = sorted(list(df.columns.values.copy()))
    df_sorted = df[pixel_values]

    # fill nans with interpolations
    for i in range(df_sorted.shape[0]):

        df_sorted.iloc[i, :] = (
            df_sorted.iloc[i, :]
            .interpolate(method="nearest", axis=0)
            .ffill()
            .bfill()
            .values
        )

    mz_length = df.shape[0]

    shift_perc = 0.1
    scale = (shift_perc * 0.01 * mz_length) / (max(pixel_values) - min(pixel_values))

    seg_size = 200

    spectra = df_sorted.values.copy()

    no_frames = spectra.shape[0]
    no_pixel_values = spectra.shape[1]

    reference = spectra[0]

    aligned_spectrum = []
    lag_vectors = []

    for i in tqdm(range(1, no_frames, 1)):
        current_hist = spectra[i]

        start_position = 0
        aligned = []

        while_loop_execution_count = 0

        while start_position <= no_pixel_values:

            end_position = start_position + (seg_size * 2)

            if end_position >= no_pixel_values:
                samseg = spectra[i, start_position:].copy()
                refseg = reference[start_position:].copy()
            else:
                # deleting -1 does not change length of vector - CAUTION
                samseg = spectra[i, start_position + seg_size : end_position - 1].copy()
                refseg = reference[start_position + seg_size : end_position - 1].copy()
                min_position = find_minimum(samseg, refseg)
                end_position = start_position + min_position + seg_size
                samseg = spectra[i, start_position:end_position]
                refseg = reference[start_position:end_position]

            shift = int(scale * pixel_values[i + int(len(samseg) / 2)])
            lag = fft_correlation(samseg, refseg, shift)
            samseg_moved = move(samseg, lag)

            aligned.extend(samseg_moved)

            start_position = end_position

        aligned_spectrum.append(aligned)
        lag_vectors.append(lag)

    aligned_spectrum = np.array(aligned_spectrum)

    return aligned_spectrum


if __name__ == "__main__":
    fire.Fire()
