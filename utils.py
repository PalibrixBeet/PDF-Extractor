import os
import pathlib
import re


def folder_info():
    """
    Get information about the current working directory and list PDF files.

    Returns:
        tuple: (path, file_list) where path is the current directory and 
               file_list is a list of PDF files in that directory
    """
    working_dir = pathlib.Path(__file__).parent.absolute()
    print(f'\nYou are here: {working_dir}')
    file_list = [path.name for path in working_dir.glob('*') if path.is_file() and path.name.endswith(".pdf")]

    print('Files from folder:', len(file_list))
    for i, file_ in enumerate(file_list):
        print(f'{i + 1}: {file_}')
    return str(working_dir).replace('\\', '/') + '/', file_list


def define_file(path, files):
    """
    Prompt user to select a PDF file either by name, ID, or absolute path.

    Args:
        path (str): Base directory path
        files (list): List of available PDF files

    Returns:
        str: Complete file path of the selected PDF
    """
    while True:
        file = input(
            '\nType or copy and paste below the name, ID or absolute path of a file\n'
            '\t(name must include file format)\n'
            '\n>>> '
        )
        if re.search(r'^[A-Z]:\\.*\.pdf$', file):
            file_path = file
        else:
            if file.isnumeric() and int(file) - 1 <= len(files):
                file = files[int(file) - 1]

            file_path = path.strip() + file.strip()

        if os.path.isfile(file_path):
            return file_path
        print(f'Invalid path: {file_path}! Please, try again')