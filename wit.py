# Upload 172
import argparse
from datetime import datetime
from distutils.dir_util import copy_tree
from functools import partial
import logging
import os
from pathlib import Path
import random
import shutil
import string
import sys
from typing import List

from dateutil.tz import tzlocal


class Commends:
    INIT = 'init'
    ADD = 'add'
    COMMIT = 'commit'

    def __init__(self) -> None:
        self.INIT
        self.ADD
        self.COMMIT


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


def generate_id():
    return ''.join(random.choices('abcdef' + string.digits, k=40))


def get_current_time():
    return datetime.now(tzlocal()).strftime("%a %b %d %H:%M:%S %Y %z")


def parse_ref(ref_path):
    return dict(line.rstrip().split('=') for line in open(ref_path) if not line.startswith("#"))


def get_previous_commit(images_path):
    ref_path = os.path.join(Path(images_path).parent, 'references.txt')
    if os.path.exists(ref_path):
        return parse_ref(ref_path).get('HEAD')
    return None


def create_commit_id_file(root, commit_id, message):
    commit_file = os.path.join(root, commit_id + '.txt')
    with open(commit_file, 'a') as fh:
        parent = get_previous_commit(root)
        current_time = get_current_time()
        data = "parent={}\ndate={}\nmessage={}\n".format(
            parent, current_time, message)
        fh.write(data)


def create_commit_id_folder(root, commit_id):
    commit_path = os.path.join(root, commit_id)
    os.mkdir(commit_path)
    return commit_path


def create_reference_file(wit_root_path, commit_id):
    ref_path = os.path.join(wit_root_path, 'references.txt')
    with open(ref_path, 'w') as fh:
        data = "HEAD={}\nmaster={}\n".format(commit_id, commit_id)
        fh.write(data)


def commit(message):
    # Check whether current working directory is under wit repo
    wit_root_path = find_repo(os.getcwd(), True)
    if wit_root_path is None:
        logging.error(
            'Not a wit repository (or any of the parent directories): {}'.format('.wit'))
        return
    # if not add.has_been_called:
    #     logging.error('No changes in repo')
    #     return
    images_path = os.path.join(wit_root_path, 'images')
    staging_path = os.path.join(wit_root_path, 'staging_area')
    # Part I - generate ID and create folder
    commit_id = generate_id()
    commit_path = create_commit_id_folder(images_path, commit_id)
    # Part II - Create metadata file
    create_commit_id_file(images_path, commit_id, message[0])
    # Part III - save staging content
    copy_tree(staging_path, commit_path)
    # Part IV - manage reference data
    create_reference_file(wit_root_path, commit_id)


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

    # create the parser for the "commit" command
    parser_commit = subparsers.add_parser(
        Commends.COMMIT, help="Create image restoration point.")
    parser_commit.add_argument("message",
                               metavar="Message",
                               nargs="+",
                               type=str,
                               help="Commit text message assigned to image.")
    parser_commit.set_defaults(func=commit)

    if len(argv) == 0:
        parser.print_help()
        return
    args = parser.parse_args(argv)
    if args.command == Commends.INIT:
        init(args.path)
    elif args.command == Commends.ADD:
        add(args.path)
    elif args.command == Commends.COMMIT:
        commit(args.message)


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
