# Upload 170
from functools import partial
import logging
import os
import sys


class Commends:
    INIT = 'init'

    def __init__(self) -> None:
        self.INIT


def makefolders(root_dir, subfolders):
    concat_path = partial(os.path.join, root_dir)
    for path in map(concat_path, subfolders):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as err:
            logging.error("Directory {} can not be created".format(path))
            raise err


def init():
    ''' Initialize wit work folders. 

    Args: None

    Raises: OSError in case folder creation is failing.

    Return: None

    Assumption - if folders exists don't do anything. 
    '''
    WORKDIR = os.getcwd()
    wit_root_path = os.path.join(WORKDIR, '.wit')
    subfolders = ('images', 'staging_area')
    makefolders(wit_root_path, subfolders)


def main():
    logging.basicConfig(filename='error.log', level=logging.ERROR)
    USAGE = '''Usage: python wit <command>
    These are common wit commands used in various situations:

    Start a working area:
        init    Create an empty wit repository or reinitialize an existing one
    '''
    if len(sys.argv) < 2:
        print(USAGE)
        return
    if sys.argv[1] == Commends.INIT:
        init()
    else:
        print('wit: "{}" is not a wit command.'.format(sys.argv[1]))


if __name__ == '__main__':
    main()
