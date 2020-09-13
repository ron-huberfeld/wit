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
from graphviz import Digraph
from termcolor import colored


class Commends:
    INIT = 'init'
    ADD = 'add'
    COMMIT = 'commit'
    STATUS = 'status'
    RM = 'rm'
    CHECKOUT = 'checkout'
    GRAPH = 'graph'
    BRANCH = 'branch'

    def __init__(self) -> None:
        self.INIT
        self.ADD
        self.COMMIT
        self.STATUS
        self.RM
        self.CHECKOUT
        self.GRAPH
        self.BRANCH


class WitException(Exception):
    def __init__(self, message):
        logging.error(message)


class WitRepo:
    def __init__(self, wit_root_path) -> None:
        self.wit_root_path = wit_root_path
        self.wit_dir = os.path.join(self.wit_root_path, '.wit')
        self.wit_images_dir = os.path.join(self.wit_dir, 'images')
        self.wit_staging_dir = os.path.join(self.wit_dir, 'staging_area')
        self.wit_references_file = os.path.join(self.wit_dir, 'references.txt')
        self.wit_active_branch_file = os.path.join(
            self.wit_dir, 'activated.txt')
        self.branches = {}

    def __str__(self) -> str:
        return 'root path: {}\nwit dir: {}\nref file: {}'.format(self.wit_root_path, self.wit_dir, self.wit_references_file)

    def update_wit_dir(self, new_root):
        self.wit_root_path = new_root
        self.wit_dir = os.path.join(self.wit_root_path, '.wit')
        self.wit_images_dir = os.path.join(self.wit_dir, 'images')
        self.wit_staging_dir = os.path.join(self.wit_dir, 'staging_area')
        self.wit_references_file = os.path.join(self.wit_dir, 'references.txt')
        self.wit_active_branch_file = os.path.join(
            self.wit_dir, 'activated.txt')

    def validate_repo_at_path(self, path, is_path_required):
        self.wit_dir = self.find_repo(path, is_path_required)
        if self.wit_dir is None:
            raise WitException(
                'Not a wit repository (or any of the parent directories): {}'.format('.wit'))
        self.update_wit_dir(Path(self.wit_dir).parent)
        return self.wit_dir

    def find_repo(self, path='.', required=False):
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
        return self.find_repo(parent, required)

    def get_references_file_data(self):
        return dict(line.rstrip().split('=') for line in open(self.wit_references_file) if not line.startswith("#"))

    def create_references_file(self, head, master, branches):
        with open(self.wit_references_file, 'w') as fh:
            data = "HEAD={}\nmaster={}\n".format(head, master)
            for branch_name, commit_id in branches.items():
                data = data + '{}={}\n'.format(branch_name, commit_id)
            fh.write(data)

    def update_references_file(self, commit_id, flow='commit'):
        head = self.get_references_file_data().get('HEAD')
        master = self.get_references_file_data().get('master')
        self.branches = self.get_branches()
        active_branch = self.get_active_branch()
        active_branch_commit_id = self.branches.get(active_branch)
        if head == active_branch_commit_id:
            # will update 'master' if active branch is 'master'
            self.branches[active_branch] = commit_id
        self.branches.pop('master')
        if flow == 'commit':
            if head == master and master == active_branch_commit_id:
                self.create_references_file(
                    commit_id, commit_id, self.branches)
            else:
                self.create_references_file(commit_id, master, self.branches)
        elif flow == 'checkout':
            if commit_id != master:
                self.create_references_file(commit_id, master, self.branches)
            else:
                self.create_references_file(
                    commit_id, commit_id, self.branches)

    def get_branches(self):
        if not os.path.exists(self.wit_references_file):
            raise WitException('Cannot read reference file.')
        self.branches = self.get_references_file_data()
        self.branches.pop("HEAD")
        return self.branches

    def update_branches(self, branch_name):
        if not os.path.exists(self.wit_references_file):
            raise WitException('Cannot read reference file.')
        head_commit_id = self.get_references_file_data().get('HEAD')
        self.branches = self.get_branches()  # branches contain 'master'
        if branch_name in self.branches:
            raise WitException(
                'Branch name "{}" already exists.'.format(branch_name))
        new_branch = {}
        new_branch[branch_name] = head_commit_id
        self.branches.update(new_branch)
        # split 'master' from branches before create file
        master = self.branches.pop('master')
        self.create_references_file(head_commit_id, master, self.branches)

    def create_active_branch_file(self, branch_name="master"):
        with open(self.wit_active_branch_file, 'w') as fh:
            fh.write(branch_name)

    def get_active_branch(self):
        with open(self.wit_active_branch_file, 'r') as fh:
            active_branch = fh.readline()
            return active_branch

    def get_current_commit_id(self):
        if os.path.exists(self.wit_references_file):
            return self.get_references_file_data().get('HEAD')
        logging.debug('No reference file exist')
        return None

    def build_commit_history(self, show_all):
        head_commit_id = self.get_current_commit_id()
        history = {}
        if head_commit_id is None:
            return history
        history['Head'] = head_commit_id
        if os.path.exists(self.wit_references_file):
            master_commit_id = self.get_references_file_data().get('master')
            if master_commit_id == head_commit_id:
                history['master'] = master_commit_id
            elif show_all:
                self.branches = self.get_branches()
                for branch, branch_commit_id in self.branches.items():
                    history[branch] = branch_commit_id
                history['master'] = master_commit_id
                history.update(self.traverse_history(
                    self.wit_images_dir, master_commit_id))
        history.update(self.traverse_history(
            self.wit_images_dir, head_commit_id))
        return history

    def get_commit_file_data(self, filename):
        return dict(line.rstrip().split('=') for line in open(filename) if not line.startswith("#"))

    def traverse_history(self, images_path, commit):
        history = {}
        while commit != 'None':
            commit_file = os.path.join(images_path, commit + '.txt')
            parent_commit_id = self.get_commit_file_data(
                commit_file).get('parent')
            if parent_commit_id != 'None':
                history[commit] = parent_commit_id
            commit = parent_commit_id
        return history

    def create_commit_id_file(self, commit_id, message):
        commit_file = os.path.join(self.wit_images_dir, commit_id + '.txt')
        with open(commit_file, 'a') as fh:
            parent = self.get_current_commit_id()
            current_time = get_current_time()
            data = "parent={}\ndate={}\nmessage={}\n".format(
                parent, current_time, message)
            fh.write(data)

    def create_commit_id_folder(self, commit_id):
        commit_path = os.path.join(self.wit_images_dir, commit_id)
        os.mkdir(commit_path)
        return commit_path

    def is_commit_id_exist(self, commit_id):
        with os.scandir(self.wit_images_dir) as images_content:
            for item in images_content:
                if item.is_dir() and commit_id == item.name:
                    return True
            return False

    def get_actual_commit_id_from_input(self, checkout_input):
        ''' Parsing checkout input to actual commit_id
        Args: checkout_input - could be either branch name (including 'master' branch) or commit id
        Raises: WitException if references files does not exist or if commit id folder was not found
        Return: valid commit id
        '''
        if checkout_input in self.get_branches():
            if not os.path.exists(self.wit_references_file):
                raise WitException('Cannot read reference file.')
            actual_commit_id = self.get_references_file_data().get(checkout_input)
            self.create_active_branch_file(checkout_input)
        else:
            actual_commit_id = checkout_input
            self.create_active_branch_file("")
        logging.warning('==> checkout {}'.format(actual_commit_id))
        if not self.is_commit_id_exist(actual_commit_id):
            raise WitException(
                'Commit ID was not found: {}'.format(actual_commit_id))
        return actual_commit_id


def detect_changes(f):
    def are_changes_exist():
        try:
            wit = WitRepo(os.getcwd())
            wit.validate_repo_at_path(os.getcwd(), True)
        except WitException:
            return
        images_path = wit.wit_images_dir
        staging_path = wit.wit_staging_dir
        last_commit_id = wit.get_current_commit_id()
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
            logging.error('No changes detected in staging to be committed.')
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
    wit = WitRepo(os.getcwd())
    wit_dir = wit.wit_dir
    subfolders = ('images', 'staging_area')
    make_folders(wit_dir, subfolders)
    wit.create_active_branch_file()


def get_relative_path(wit_root: Path, target: Path, is_file: bool) -> Path:
    if is_file:
        return target.parent.relative_to(wit_root.parent)
    return target.relative_to(wit_root.parent)


def handle_path_addition(wit_root_path, path_item):
    realpath = os.path.realpath(path_item)
    path = Path(realpath)
    wit_root = Path(wit_root_path)
    staging_path = os.path.join(wit_root_path, 'staging_area')
    if os.path.isfile(path):
        relative_path = get_relative_path(wit_root, path, True)
        Path(os.path.join(staging_path, relative_path)).mkdir(
            exist_ok=True, parents=True)
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
        try:
            wit_root_path = WitRepo(
                os.getcwd()).validate_repo_at_path(path_item, True)
        except WitException:
            return
        handle_path_addition(wit_root_path, path_item)


def generate_id():
    return ''.join(random.choices('abcdef' + string.digits, k=40))


def get_current_time():
    return datetime.now(tzlocal()).strftime("%a %b %d %H:%M:%S %Y %z")


@detect_changes
def commit(message):
    message = message[0]
    # Check whether current working directory is under wit repo
    try:
        wit = WitRepo(os.getcwd())
        wit.validate_repo_at_path(os.getcwd(), True)
    except WitException:
        return
    staging_path = wit.wit_staging_dir
    # Part I - generate ID and create folder
    commit_id = generate_id()
    commit_path = wit.create_commit_id_folder(commit_id)
    # Part II - Create metadata file
    wit.create_commit_id_file(commit_id, message)
    # Part III - save staging content
    copy_tree(staging_path, commit_path)
    # Part IV - manage reference data
    ref_path = wit.wit_references_file
    if os.path.exists(ref_path):
        wit.update_references_file(commit_id)
    else:
        wit.create_references_file(commit_id, commit_id, wit.branches)


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
    try:
        wit = WitRepo(os.getcwd())
        wit_root_path = wit.validate_repo_at_path(os.getcwd(), True)
    except WitException:
        return
    images_path = wit.wit_images_dir
    staging_path = wit.wit_staging_dir
    last_commit_id = wit.get_current_commit_id()
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
        try:
            wit_root_path = WitRepo(
                os.getcwd()).validate_repo_at_path(path_item, True)
        except WitException:
            return
        handle_path_removal(wit_root_path, path_item)


def merge_override_tree(sourceRoot, destRoot):
    # https://stackoverflow.com/questions/22588225/how-do-you-merge-two-directories-or-move-with-replace-from-the-windows-command
    ''' Updates destination and override existing files.

    Args:
        sourceRoot: source root folder of files to copy
        destRoot:   Destination root folder for files to be created
    '''
    for path, _, files in os.walk(sourceRoot):
        relPath = os.path.relpath(path, sourceRoot)
        destPath = os.path.join(destRoot, relPath)
        if not os.path.exists(destPath):
            try:
                os.makedirs(destPath)
            except OSError as err:
                raise err
        for file in files:
            destFile = os.path.join(destPath, file)
            srcFile = os.path.join(path, file)
            shutil.copy(srcFile, destFile)


def checkout(commit_id):
    commit_id = commit_id[0]
    print('checkout {}'.format(commit_id))
    try:
        wit = WitRepo(os.getcwd())
        wit_root_path = wit.validate_repo_at_path(os.getcwd(), True)
    except WitException:
        return
    images_path = wit.wit_images_dir
    staging_path = wit.wit_staging_dir
    try:
        commit_id = wit.get_actual_commit_id_from_input(commit_id)
    except WitException:
        return
    # Check if uncommitted files and unstaged files exist
    last_commit_id = wit.get_current_commit_id()
    last_commit_id_folder = os.path.join(images_path, last_commit_id)
    if get_changes_to_be_committed(staging_path, last_commit_id_folder, False) or get_changes_not_committed(Path(wit_root_path).parent, staging_path, False):
        logging.error('Uncommitted work found, blocking checkout')
        return
    # Copy and override image's files, one by one, to their original location
    source_commit_id_path = os.path.join(images_path, commit_id)
    working_dir_target = Path(wit_root_path).parent
    merge_override_tree(source_commit_id_path, working_dir_target)
    merge_override_tree(source_commit_id_path, staging_path)
    ref_path = wit.wit_references_file
    if os.path.exists(ref_path):
        wit.update_references_file(commit_id, 'checkout')


def generate_graph(commits_history, branches, active_branch):
    graph = Digraph(name='wit_graph')
    for k, v in commits_history.items():
        graph.edge(k, v)
        if k in branches:
            graph.node(k, shape="plaintext")
            if k == active_branch:
                graph.node(k, label="{}*".format(k))
    graph.graph_attr['rankdir'] = 'LR'
    graph.edge_attr.update(arrowhead='vee', arrowsize='2')
    graph.node('Head', shape="plaintext")
    print(graph.source)
    graph.view()


def graph(show_all):
    wit = WitRepo(os.getcwd())
    try:
        wit.validate_repo_at_path(os.getcwd(), True)
    except WitException:
        return
    commits_history = wit.build_commit_history(show_all)
    branches = wit.get_branches()
    active_branch = wit.get_active_branch()
    generate_graph(commits_history, branches, active_branch)


def branch(name):
    branch_name = name[0]
    try:
        wit = WitRepo(os.getcwd())
        wit.validate_repo_at_path(os.getcwd(), True)
    except WitException:
        return
    # add row to references.txt : name = commit_id from head
    try:
        wit.update_branches(branch_name)
    except WitException:
        return


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
        Commends.STATUS, help="View repository status.")
    parser_status.set_defaults(func=status)

    # create the parser for the "rm" command
    parser_rm = subparsers.add_parser(
        Commends.RM, help="Remove files from staging area.")
    parser_rm.add_argument("path",
                           metavar="path",
                           nargs="+",
                           help="File or folder to remove from staging.")
    parser_rm.set_defaults(func=rm)

    # create the parser for the "checkout" command
    parser_checkout = subparsers.add_parser(
        Commends.CHECKOUT, help="Move to a different image.")
    parser_checkout.add_argument("commit_id",
                                 metavar="Commit ID",
                                 nargs="+",
                                 type=str,
                                 help="Commit ID which mark the image restoration point.")
    parser_checkout.set_defaults(func=checkout)

    # create the parser for the "graph" command
    parser_graph = subparsers.add_parser(
        Commends.GRAPH, help="Display wit commits graph.")
    parser_graph.add_argument("--all",
                              metavar="all commits",
                              nargs="?",
                              const=True,
                              default=False,
                              help="show all commits history.")
    parser_graph.set_defaults(func=graph)

    # create the parser for the "branch" command
    parser_branch = subparsers.add_parser(
        Commends.BRANCH, help="Create a branch tag.")
    parser_branch.add_argument("name",
                               metavar="name",
                               nargs="+",
                               help="branch name")
    parser_branch.set_defaults(func=branch)

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
    elif args.command == Commends.CHECKOUT:
        checkout(args.commit_id)
    elif args.command == Commends.GRAPH:
        graph(args.all)
    elif args.command == Commends.BRANCH:
        branch(args.name)


def configure_logging():
    file_handler = logging.FileHandler('error.log', 'a')
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S %p')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def check_dependencies():
    # https://github.com/functicons/git-graph/blob/master/git-graph.py
    if not shutil.which('dot'):
        logging.error(
            'Command "dot" was not found, visual graph will not be available.')


def main(argv=sys.argv[1:]):
    check_dependencies()
    configure_logging()
    parse_input(argv)


if __name__ == '__main__':
    main()
