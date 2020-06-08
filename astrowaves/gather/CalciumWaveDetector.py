import numpy as np
import os
import skimage
from skimage import measure
from joblib import Parallel, delayed
from tqdm import tqdm


class CalciumWaveDetector():

    def __init__(self):
        pass

    def _indices_label(self, array, label):
        return np.argwhere(array == label)

    def run(self, waves):
        waves_labelled = measure.label(waves, connectivity=3).astype('uint16')
        uniq, counts = np.unique(waves_labelled, return_counts=True)
        labels = uniq[1:]
        counts = counts[1:]
        label_counts = list(zip(labels, counts))
        count_filtered = list(filter(lambda x: x[1] > 30, label_counts))
        labels, counts = zip(*count_filtered)
        object_cords = Parallel(n_jobs=3, verbose=10)(delayed(self._indices_label)
                                                      (waves_labelled, label) for label in labels)
        return object_cords

    def run2(self, waves):
        slices = [slic for slic in range(waves.shape[2]) if not np.any(waves[:, :, slic])]
        length = waves.shape[2]
        to_slice = [int(length / 4), int(length / 2), int(3 * length / 4)]
        def func(myList, myNumber): return min(myList, key=lambda x: abs(x - myNumber))
        out = list(map(lambda x: func(slices, x), to_slice))
        out = [0, *out, length]

        total = []

        for index in tqdm(range(len(out) - 1)):
            current = waves[:, :, out[index]:out[index + 1]]
            print(out[index + 1])
            labelled = measure.label(current, connectivity=3).astype('uint16')
            last_slice = index
            uniq, counts = np.unique(labelled, return_counts=True)
            labels = uniq[1:]
            counts = counts[1:]
            print(len(labels))
            print(len(counts))
            label_counts = list(zip(labels, counts))
            count_filtered = list(filter(lambda x: x[1] > 30, label_counts))
            labels, counts = zip(*count_filtered)
            object_cords = Parallel(n_jobs=3, verbose=10)(delayed(self._indices_label)
                                                          (labelled, label) for label in labels)
            total.extend(object_cords)
        return total


def debug():
    debug_path = '/app/data/output_data'
    waves = np.load(os.path.join(debug_path, "waves_morph.npy"))
    detector = CalciumWaveDetector()
    waves_inds = detector.run(waves)
    import pickle

    with open(os.path.join(debug_path, 'waves_inds.pck'), 'wb') as file:
        pickle.dump(waves_inds, file)


def main():
    debug_path = '/app/data/output_data'

    waves = np.load(os.path.join(debug_path, "waves_morph.npy"))
    detector = CalciumWaveDetector()
    waves_inds = detector.run2(waves)
    import pickle

    with open(os.path.join(debug_path, 'waves_inds.pck'), 'wb') as file:
        pickle.dump(waves_inds, file)


if __name__ == '__main__':

    main()
