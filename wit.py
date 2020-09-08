import argparse
from distutils.dir_util import copy_tree
from functools import partial
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import List


class Commends:
    INIT = 'init'
    ADD = 'add'

    def __init__(self) -> None:
        self.INIT
        self.ADD


def make_folders(root_dir, subfolders):
    concat_path = partial(os.path.join, root_dir)
    for path in map(concat_path, subfolders):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as err:
            logging.error("Directory {} can not be created".format(path))
            raise err


def init(args):
    ''' Initialize wit work folders.

    Args: None

    Raises: OSError in case folder creation is failing.

    Return: None

    Assumption - if folders exists don't do anything.
    '''
    WORKDIR = os.getcwd()
    wit_root_path = os.path.join(WORKDIR, '.wit')
    subfolders = ('images', 'staging_area')
    make_folders(wit_root_path, subfolders)


def find_repo(path='.', required=False):
    path = os.path.realpath(path)
    if os.path.isdir(os.path.join(path, '.wit')):
        if required:
            return os.path.join(path, '.wit')
        return True
    parent = os.path.realpath(os.path.join(path, ".."))
    if parent == path:
        if required:
            return None
        return False
    return find_repo(parent, required)


def get_relative_path(wit_root: Path, target: Path, is_file: bool) -> Path:
    if is_file:
        return target.parent.relative_to(wit_root.parent)
    return target.relative_to(wit_root.parent)


def handle_path_addition(wit_root_path, path_item):
    realpath = os.path.realpath(path_item)
    path = Path(realpath)
    wit_root = Path(wit_root_path)
    staging_path = os.path.join(wit_root, 'staging_area')
    if os.path.isfile(path):
        relative_path = get_relative_path(wit_root, path, True)
        shutil.copy2(path_item, os.path.join(staging_path, relative_path))
    else:
        relative_path = get_relative_path(wit_root, path, False)
        copy_tree(path_item, os.path.join(staging_path, relative_path))


def add(paths: List[str]):
    # Check whether the path is valid and is under wit repo
    for path_item in paths:
        if not os.path.exists(path_item):
            logging.error(
                'Path "{}" did not match any files'.format(path_item))
            return
        wit_root_path = find_repo(path_item, True)
        if wit_root_path is None:
            logging.error(
                'Not a wit repository (or any of the parent directories): {}'.format('.wit'))
            return
        handle_path_addition(wit_root_path, path_item)


def parse_input(argv):
    # create the top-level parser
    parser = argparse.ArgumentParser(
        prog='python wit', description="These are common wit commands used in various situations:", usage='%(prog)s')
    subparsers = parser.add_subparsers(
        title='Valid commands', dest="command")
    subparsers.required = True

    # create the parser for the "init" command
    parser_init = subparsers.add_parser(
        Commends.INIT, help="Create an empty wit repository or reinitialize an existing one.")
    parser_init.add_argument("path",
                             metavar="path",
                             nargs="?",
                             default=".",
                             help="Location to create the wit repository.")
    parser_init.set_defaults(func=init)

    # create the parser for the "add" command
    parser_add = subparsers.add_parser(
        Commends.ADD, help="Add a file or a folder content into staging area.")
    parser_add.add_argument("path",
                            metavar="file or folder",
                            nargs="+",
                            default=".",
                            help="file or folder to add to repo.")
    parser_add.set_defaults(func=add)
    if len(argv) == 0:
        parser.print_help()
        return
    args = parser.parse_args(argv)
    if args.command == Commends.INIT:
        init(args.path)
    elif args.command == Commends.ADD:
        add(args.path)


def configure_logging():
    file_handler = logging.FileHandler('error.log', 'a')
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S %p')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def main(argv=sys.argv[1:]):
    configure_logging()
    parse_input(argv)


if __name__ == '__main__':
    main()
