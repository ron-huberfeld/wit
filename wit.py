import argparse
from datetime import datetime
from distutils.dir_util import copy_tree
from filecmp import dircmp
from functools import partial
from functools import wraps
import logging
import os
from pathlib import Path
import random
import shutil
import string
import sys
from typing import List

from dateutil.tz import tzlocal
from termcolor import colored


class Commends:
    INIT = 'init'
    ADD = 'add'
    COMMIT = 'commit'
    STATUS = 'status'
    RM = 'rm'

    def __init__(self) -> None:
        self.INIT
        self.ADD
        self.COMMIT
        self.STATUS
        self.RM


def detect_changes(f):
    def are_changes_exist():
        wit_root_path = find_repo(os.getcwd(), True)
        if wit_root_path is None:
            logging.error(
                'Not a wit repository (or any of the parent directories): {}'.format('.wit'))
            return
        images_path = os.path.join(wit_root_path, 'images')
        staging_path = os.path.join(wit_root_path, 'staging_area')
        last_commit_id = get_current_commit_id(images_path)
        if last_commit_id is None:
            return True
        last_commit_id_folder = os.path.join(images_path, last_commit_id)
        if get_changes_to_be_committed(staging_path, last_commit_id_folder, False):
            return True
        return False

    @wraps(f)
    def decorated(*args, **kwargs):
        changes_exist = are_changes_exist()
        if not changes_exist:
            print('No changes detected in staging to be committed.')
            return
        return f(*args, **kwargs)
    return decorated


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


def parse_reference_file(ref_path):
    return dict(line.rstrip().split('=') for line in open(ref_path) if not line.startswith("#"))


def get_current_commit_id(images_path):
    ref_path = os.path.join(Path(images_path).parent, 'references.txt')
    if os.path.exists(ref_path):
        return parse_reference_file(ref_path).get('HEAD')
    logging.info('No reference file exist')
    return None


def create_commit_id_file(images_path, commit_id, message):
    commit_file = os.path.join(images_path, commit_id + '.txt')
    with open(commit_file, 'a') as fh:
        parent = get_current_commit_id(images_path)
        current_time = get_current_time()
        data = "parent={}\ndate={}\nmessage={}\n".format(
            parent, current_time, message)
        fh.write(data)


def create_commit_id_folder(images_path, commit_id):
    commit_path = os.path.join(images_path, commit_id)
    os.mkdir(commit_path)
    return commit_path


def create_reference_file(wit_root_path, commit_id):
    ref_path = os.path.join(wit_root_path, 'references.txt')
    with open(ref_path, 'w') as fh:
        data = "HEAD={}\nmaster={}\n".format(commit_id, commit_id)
        fh.write(data)


@detect_changes
def commit(message):
    # Check whether current working directory is under wit repo
    wit_root_path = find_repo(os.getcwd(), True)
    if wit_root_path is None:
        logging.error(
            'Not a wit repository (or any of the parent directories): {}'.format('.wit'))
        return
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


def get_modified_files(dcmp):
    modified_files = []
    for items in dcmp.diff_files:
        modified_files.append(os.path.join(dcmp.left, items))
    for sub_items in dcmp.subdirs.values():
        modified_files.extend(get_modified_files(sub_items))
    return modified_files


def get_new_files(dcmp):
    new_files = []
    for items in dcmp.left_only:
        new_files.append(os.path.join(dcmp.left, items))
    for sub_items in dcmp.subdirs.values():
        new_files.extend(get_new_files(sub_items))
    return new_files


def get_deleted_files(dcmp):
    deleted_files = []
    for items in dcmp.right_only:
        deleted_files.append(os.path.join(dcmp.left, items))
    for sub_items in dcmp.subdirs.values():
        deleted_files.extend(get_deleted_files(sub_items))
    return deleted_files


def get_changes_to_be_committed(stage_area, last_commit, required=True):
    # Compare content of staging area to last commit id folder
    if last_commit is None:
        last_commit = os.path.join(Path(stage_area).parent, "images")
    dcmp = dircmp(stage_area, last_commit)
    list_of_modified_files = get_modified_files(dcmp)
    list_of_new_files = get_new_files(dcmp)
    if len(list_of_modified_files) + len(list_of_new_files) == 0:
        if required:
            return '\tNo changes detected\n'
        return False
    if required:
        return '\n'.join(colored('\tnew file:\t' + os.path.relpath(item, stage_area), 'green') for item in list_of_new_files) + '\n' + '\n'.join(colored('\tmodified file:\t' + os.path.relpath(item, stage_area), 'yellow') for item in list_of_modified_files) + '\n'
    return True


def get_changes_not_committed(workdir, stage_area, required=True):
    # Compare content of actual working directory to the staging area
    dcmp = dircmp(workdir, stage_area, ignore=['.wit'])
    list_of_modified_files = get_modified_files(dcmp)
    printable_modified_files = (colored('\tmodified file:\t' + os.path.relpath(
        Path(item), os.getcwd()), 'yellow') for item in list_of_modified_files)
    list_of_deleted_files = get_deleted_files(dcmp)
    printable_deleted_files = (
        colored('\tdeleted file:\t' + os.path.relpath(item, os.getcwd()), 'red') for item in list_of_deleted_files)
    if len(list_of_modified_files) + len(list_of_deleted_files) == 0:
        if required:
            return '\tNo changes detected\n'
        return False
    if required:
        return '\n'.join(printable_modified_files) + '\n' + '\n'.join(printable_deleted_files) + '\n'
    return True


def get_untracked_files(workdir, stage_area):
    # Compare actual working directory to the staging area to find new files which are not in staging
    dcmp = dircmp(workdir, stage_area, ignore=['.wit'])
    list_of_new_files = get_new_files(dcmp)
    printable_new_files = (
        colored('\t' + os.path.relpath(item, os.getcwd()), 'red') for item in list_of_new_files)
    return '\n'.join(printable_new_files)


def status():
    # Check whether current working directory is under wit repo
    wit_root_path = find_repo(os.getcwd(), True)
    if wit_root_path is None:
        logging.error(
            'Not a wit repository (or any of the parent directories): {}'.format('.wit'))
        return
    images_path = os.path.join(wit_root_path, 'images')
    staging_path = os.path.join(wit_root_path, 'staging_area')
    last_commit_id = get_current_commit_id(images_path)
    if last_commit_id is None:
        print('No commits yet\n\nChanges to be committed:\n{}\nChanges not staged for commit:\n{}\nUntracked files:\n{}\n'.format(
            get_changes_to_be_committed(staging_path, None), get_changes_not_committed(Path(wit_root_path).parent, staging_path), get_untracked_files(Path(wit_root_path).parent, staging_path)))
    else:
        last_commit_id_folder = os.path.join(images_path, last_commit_id)
        print('Current commit ID: {}\nChanges to be committed:\n{}\nChanges not staged for commit:\n{}\nUntracked files:\n{}\n'.format(
            last_commit_id, get_changes_to_be_committed(staging_path, last_commit_id_folder), get_changes_not_committed(Path(wit_root_path).parent, staging_path), get_untracked_files(Path(wit_root_path).parent, staging_path)))


def handle_path_removal(wit_root_path, path_item):
    staging_path = os.path.join(wit_root_path, 'staging_area')
    path_to_delete = os.path.join(staging_path, path_item)
    if not os.path.exists(path_to_delete):
        logging.error('File to delete from staging was not there.')
        return
    if os.path.isfile(path_to_delete):
        print('deleting file: {}'.format(path_to_delete))
        os.remove(path_to_delete)
    else:
        print('deleting folder: {}'.format(path_to_delete))
        shutil.rmtree(path_to_delete)


def rm(paths):
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
        handle_path_removal(wit_root_path, path_item)


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
                            metavar="path",
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
                               help="Commit text message assigned to image.")
    parser_commit.set_defaults(func=commit)

    # create the parser for the "status" command
    parser_status = subparsers.add_parser(
        Commends.STATUS, help="View repository status")
    parser_status.set_defaults(func=status)

    # create the parser for the "rm" command
    parser_rm = subparsers.add_parser(
        Commends.RM, help="Remove files from staging area.")
    parser_rm.add_argument("path",
                           metavar="path",
                           nargs="+",
                           help="File or folder to remove from staging.")
    parser_rm.set_defaults(func=rm)

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
    elif args.command == Commends.STATUS:
        status()
    elif args.command == Commends.RM:
        rm(args.path)


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
