import os
import shutil
import argparse


class CleanupMetadata:
    def run(self, directory):
        """Cleans up metadata generated during the task

        Parameters
        ----------
        directory : str
            A directory for a given timelapse
        """
        # shutil.rmtree(os.path.join(directory, 'image_sequence'))
        # os.remove(os.path.join(directory, 'waves.npy'))
        os.remove(os.path.join(directory, "waves_inds.pck"))


def cleanup(input_path):
    cm = CleanupMetadata()
    cm.run(input_path)


def main():
    args = parse_args()
    directory = args.directory
    rootdir = args.rootdir
    dir_path = os.path.join(rootdir, directory)
    cm = CleanupMetadata()
    cm.run(dir_path)


def parse_args():
    parser = argparse.ArgumentParser(prog="maskgenerator")
    parser.add_argument("--directory", help="output_directory")
    parser.add_argument(
        "--rootdir", type=str, default="/app/data", help="root directory of files"
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    main()
