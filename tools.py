from termcolor import colored


def print_error(text):
    print(colored(text, 'red'))


def print_info(text):
    print(colored(text, 'green'))