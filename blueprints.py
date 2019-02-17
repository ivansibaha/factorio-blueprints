#!/usr/bin/env python
"""
Command line tool to manage blueprint strings from the game Factorio (https://www.factorio.com/)
"""

from __future__ import print_function

import argparse
import base64
import ConfigParser
import json
import re
import os
import sys
import zlib




CONFIG_FILE = 'config.ini'
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
BLUEPRINT_SUPPORTED_VERSIONS = [0]


try:
    config = ConfigParser.RawConfigParser()
    config.read(os.path.join(SCRIPT_PATH, CONFIG_FILE))

    BLUEPRINT_VERSION = config.getint('blueprints', 'version')
    DB_PATH = config.get('blueprints-db', 'location')
    NO_BOOK_NAME = config.get('blueprints-db', 'not_a_book_special_folder')
    VERSION_FILE = config.get('blueprints-db', 'version_file')
except Exception as err:
    print('Error parsing ' + CONFIG_FILE + ': ' + str(err))
    sys.exit(-1)




def full_db_path(db_path = DB_PATH):
    return os.path.join(SCRIPT_PATH, db_path)


def create_db_directories(db_path = DB_PATH, not_a_book = NO_BOOK_NAME):
    """create DB if not existing"""
    db_directory = full_db_path(db_path)
    if not os.path.exists(db_directory):
        print('Make directory: ' + db_directory)
        os.makedirs(db_directory)
    db_not_a_book_directory = os.path.join(db_directory, not_a_book)
    if not os.path.exists(db_not_a_book_directory):
        print('Make directory: ' + db_not_a_book_directory)
        os.makedirs(db_not_a_book_directory)


def parse_blueprint_string(blueprint_str):
    assert int(blueprint_str[0]) in BLUEPRINT_SUPPORTED_VERSIONS, 'Blueprint version number ' + blueprint_str[0] + ' is not among the supported versions: ' + str(BLUEPRINT_SUPPORTED_VERSIONS)
    return zlib.decompress(base64.b64decode(blueprint_str[1:]))


def generate_blueprint_string(blueprint_json):
    return str(BLUEPRINT_VERSION) + base64.b64encode(zlib.compress(blueprint_json))


blueprint_filename_pattern = re.compile('^(([0-9]{3,}) - )?(.*)\.json$')


def parse_blueprint_filename(filename):
    match = blueprint_filename_pattern.match(filename)
    if match:
        index = int(match.group(2)) if match.group(2) else -1
        return { 'index': index,  'name': match.group(3), 'filename': filename }
    else:
        return None

def generate_blueprint_filename(name, index = -1):
    prefix = '{0:03d} - '.format(index) if index >= 0 else ''
    return prefix + name + '.json'


def delete_book_content(book_directory):
    for file in os.listdir(book_directory):
        file_path = os.path.join(book_directory, file)
        try:
            if os.path.isfile(file_path):
                filename = os.path.basename(file_path)
                if filename[-5:] == '.json' or filename == VERSION_FILE:
                    os.unlink(file_path)
        except Exception as err:
            print('Error deleting blueprint file [' + file_path + ']: ' + str(err))


def store_blueprint_book(book_obj, db_path = DB_PATH):
    book_name = book_obj['blueprint_book']['label'] if 'label' in book_obj['blueprint_book'].keys() else 'no-name'

    # Create blueprint book folder, or erase its content if existing
    db_book_directory = os.path.join(full_db_path(db_path), book_name)
    if not os.path.exists(db_book_directory):
        print('Book Created: ' + db_book_directory)
        os.makedirs(db_book_directory)
    else:
        print('Book Updated: ' + db_book_directory)
        delete_book_content(db_book_directory)

    # Create or update individual blueprints
    for blueprint_elt in book_obj['blueprint_book']['blueprints']:
        blueprint_obj = { 'blueprint' : blueprint_elt['blueprint'] }
        blueprint_index = blueprint_elt['index']
        try:
            store_single_blueprint(blueprint_obj, blueprint_index, book_name, db_path)
        except Exception as err:
            print('Error writing blueprint file: ' + str(err))

    # Version text file
    store_book_version(book_obj['blueprint_book']['version'], book_name, db_path)


def store_single_blueprint(blueprint_obj, blueprint_index = -1, book_name = NO_BOOK_NAME, db_path = DB_PATH):
    assert blueprint_index >= 0 or book_name == NO_BOOK_NAME, 'Cannot add an individual blueprint to a book yet'
    blueprint_name = blueprint_obj['blueprint']['label'] if 'label' in blueprint_obj['blueprint'].keys() else 'no-name'
    rel_db_path = os.path.join(book_name, generate_blueprint_filename(blueprint_name, blueprint_index))
    full_path = os.path.join(full_db_path(db_path), rel_db_path)
    if os.path.exists(full_path):
        print('Blueprint Updated: ' + rel_db_path)
    else:
        print('Blueprint Created: ' + rel_db_path)
    fp = open(full_path, 'w')
    json.dump(blueprint_obj, fp, sort_keys=True, indent=2, separators=(',', ': '))
    fp.close()


def read_book_version(book_name, db_path = DB_PATH):
    assert book_name != NO_BOOK_NAME, 'Only valid blueprint books have a version file'
    rel_db_path = os.path.join(book_name, VERSION_FILE)
    full_path = os.path.join(full_db_path(db_path), rel_db_path)
    fp = open(full_path, 'r')
    version = int(fp.read().strip())
    fp.close()
    return version


def store_book_version(version, book_name, db_path = DB_PATH):
    assert book_name != NO_BOOK_NAME, 'Only valid blueprint books have a version file'
    rel_db_path = os.path.join(book_name, VERSION_FILE)
    full_path = os.path.join(full_db_path(db_path), rel_db_path)
    fp = open(full_path, 'w')
    fp.write(str(version) + '\n')
    fp.close()


def store_from_string(blueprint_raw_string, book_name = NO_BOOK_NAME, db_path = DB_PATH):
    result = 0
    try:
        blueprint_json = parse_blueprint_string(blueprint_raw_string)
        blueprint_obj = json.loads(blueprint_json)
        if 'blueprint_book' in blueprint_obj.keys():
            assert book_name == NO_BOOK_NAME, 'Cannot store a blueprint book in another blueprint book'
            store_blueprint_book(blueprint_obj, db_path)
        elif 'blueprint' in blueprint_obj.keys():
            store_single_blueprint(blueprint_obj, -1, book_name, db_path)
        else:
            print('ParsingError: Could not identify the type of blueprint ' + blueprint_obj.keys())
            result = -1
    except AssertionError as err:
        print('AssertionError: ' + str(err))
        return -1
    except IOError as err:
        print('IOError: ' + str(err))
        return -1
    except Exception as err:
        print('Exception: ' + str(err))
        return -1

    return result


def db_book_exists(book_name, db_path = DB_PATH):
    book_path = os.path.join(full_db_path(db_path), book_name)
    return os.path.exists(book_path)


def get_book_contents(book_name, db_path = DB_PATH):
    contents = []
    book_path = os.path.join(full_db_path(db_path), book_name)
    assert os.path.exists(book_path), 'Path does not exist [' + book_path + ']'
    for file in os.listdir(book_path):
        file_path = os.path.join(book_path, file)
        if os.path.isfile(file_path):
            contents.append(parse_blueprint_filename(file))
    return [a for a in contents if a is not None]


def list_book(contents, book_name):
    if contents:
        if book_name == NO_BOOK_NAME:
            print('Individual Blueprints:')
        else:
            print('Blueprint Book: ' + book_name + '/')
        for bp_parsed_file in contents:
            print(' >> ' + bp_parsed_file['filename'])


def list_db_all(db_path = DB_PATH):
    single_blueprints = []
    for file in os.listdir(full_db_path(db_path)):
        contents = []
        if file == NO_BOOK_NAME:
            # Print that one last
            single_blueprints = get_book_contents(NO_BOOK_NAME, db_path)
        elif file[0] != '.' and os.path.isdir(os.path.join(full_db_path(db_path), file)):
            contents = get_book_contents(file, db_path)
        list_book(contents, file)
    list_book(single_blueprints, NO_BOOK_NAME)


def list_db_book(book_name = NO_BOOK_NAME, db_path = DB_PATH):
    contents = get_book_contents(book_name, db_path)
    list_book(contents, book_name)


def get_book_in_json(book_name, contents, version, active_index = 0):
    assert contents, 'Empty book [' + book_name + ']'
    blueprints = [{'blueprint': bp_parsed_file['blueprint'], 'index': bp_parsed_file['index']} for bp_parsed_file in contents]
    blueprint_book = { 'blueprint_book': {
        'active_index': active_index,
        'blueprints': blueprints,
        'item': 'blueprint-book',
        'label': book_name,
        'version': version
    }}
    # Ensure the most compact JSON format
    json_string = json.dumps(blueprint_book, sort_keys=True, separators=(',', ':'))
    return json_string


def get_db_book_in_json(book_name, db_path = DB_PATH):
    assert book_name != NO_BOOK_NAME, 'Can only decode a valid blueprint book'
    contents = get_book_contents(book_name, db_path)
    for bp_parsed_file in contents:
        rel_db_path = os.path.join(book_name, bp_parsed_file['filename'])
        full_path = os.path.join(full_db_path(db_path), rel_db_path)
        fp = open(full_path, 'r')
        bp_parsed_file['blueprint'] = json.load(fp)['blueprint']
        fp.close()
    version = read_book_version(book_name, db_path)
    return get_book_in_json(book_name, contents, version)


def get_encoded_db_book(book_name, db_path = DB_PATH):
    return generate_blueprint_string(get_db_book_in_json(book_name, db_path))


def process_blueprint_string(blueprint_string, stdout = False, book_name = NO_BOOK_NAME, db_path = DB_PATH):
    if stdout:
        print(parse_blueprint_string(blueprint_string))
    else:
        store_from_string(blueprint_string, book_name, db_path)


def match_filename(files):
    for json_file in files:
        if not os.path.exists(json_file) or not os.path.isfile(json_file):
            print("Error: Skip [" + json_file + "]. File does not exist.")
            continue
        blueprint_info = parse_blueprint_filename(os.path.basename(json_file))
        if not blueprint_info:
            print("Error: Skip [" + json_file + "]. Expect JSON files with option --match-filename.")
            continue
        fp = open(json_file, 'r')
        blueprint_obj = json.load(fp)
        fp.close()
        if not blueprint_obj or 'blueprint' not in blueprint_obj:
            print("Error: Skip [" + json_file + "]. Wrong blueprint format.")
            continue
        if 'label' not in blueprint_obj['blueprint'] or blueprint_obj['blueprint']['label'] != blueprint_info['name']:
            print('Rename blueprint in [' + blueprint_info['name'] + '].')
            blueprint_obj['blueprint']['label'] = blueprint_info['name']
            fp = open(json_file, 'w')
            json.dump(blueprint_obj, fp, sort_keys=True, indent=2, separators=(',', ': '))
            fp.close()




def main():
    result = 0
    parser = argparse.ArgumentParser(description='Manage blueprint strings from the game Factorio (https://www.factorio.com/)')
    parser.add_argument('files', metavar='FILE', nargs='*', help='Input files for options -f and -r')
    parser.add_argument('-s', '--from-strings', metavar='raw_string', dest='blueprint_strings', nargs='+', help='Store blueprints from raw strings')
    parser.add_argument('-f', '--from-files', dest='blueprint_files', action='store_true', help='Store blueprints from files, one raw string per line')
    parser.add_argument('-b', '--book-name', metavar='book', dest='blueprint_book_name', default = NO_BOOK_NAME, help='Name of a blueprint book')
    parser.add_argument('-l', '--list', dest='list_db', action='store_true', help='List database content')
    parser.add_argument('-r', '--raw', dest='raw', action='store_true', help='Print out book or json file as a blueprint string')
    parser.add_argument('--json', dest='json', action='store_true', help='Print out the blueprints as JSON strings')
    parser.add_argument('--match-filename', dest='match_filename', action='store_true', help='Force the blueprint name to match the filename (without the index)')
    args = parser.parse_args()

    create_db_directories()

    if args.blueprint_book_name != NO_BOOK_NAME and not db_book_exists(args.blueprint_book_name):
        print('Error: Blueprint book does not exists in the database [' + args.blueprint_book_name + ']')
        return -1

    try:
        if args.match_filename:
            # Blueprint edition commands
            assert not args.blueprint_files, 'Incompatible option -f with a blueprint edition command'
            assert not args.blueprint_files, 'Incompatible option -s with a blueprint edition command'
            assert not args.list_db, 'Incompatible option -l with a blueprint edition command'
            assert not args.raw, 'Incompatible option -r with a blueprint edition command'
            if args.match_filename:
                assert args.blueprint_book_name == NO_BOOK_NAME, 'Imcompatible options --match-filename and --book-name'
                assert args.files, 'Must provide one or several blueprint JSON files with --match-filename'
                match_filename(args.files)
        else:
            # Blueprint store/load blueprints and blueprint books
            if args.blueprint_strings:
                assert not args.blueprint_files, 'Incompatible options -s and -f'
                assert not args.list_db, 'Incompatible options -s and -l'
                assert not args.raw, 'Incompatible options -s and -r'
                for blueprint_string in args.blueprint_strings:
                    process_blueprint_string(blueprint_string, args.json, args.blueprint_book_name)
            elif args.blueprint_files:
                assert not args.list_db, 'Incompatible options -f and -l'
                assert not args.raw, 'Incompatible options -f and -r'
                assert args.files, 'No file specified with option -f'
                for blueprint_file in args.files:
                    if not args.json:
                        print('Opening file: ' + blueprint_file)
                    fp = open(blueprint_file, 'r')
                    for blueprint_string in fp:
                        process_blueprint_string(blueprint_string.strip(), args.json, args.blueprint_book_name)
            elif args.list_db:
                assert not args.raw, 'Incompatible options -l and -r'
                if args.blueprint_book_name == NO_BOOK_NAME:
                    list_db_all()
                else:
                    list_db_book(args.blueprint_book_name)
            elif args.raw:
                if args.blueprint_book_name == NO_BOOK_NAME:
                    assert args.files, 'No file or blueprint book specified with option -r'
                    for json_file in args.files:
                        assert json_file[-5:] == '.json', 'Expect JSON files with option -r, but got [' +  json_file + ']'
                        fp = open(json_file, 'r')
                        # Ensure the most compact JSON format
                        json_string = json.dumps(json.load(fp), sort_keys=True, separators=(',', ':'))
                        print(generate_blueprint_string(json_string))
                        fp.close()
                else:
                    print(get_encoded_db_book(args.blueprint_book_name))
            elif args.json and args.blueprint_book_name != NO_BOOK_NAME:
                print(get_db_book_in_json(args.blueprint_book_name))
            else:
                print("Error: Wrong arguments")
                parser.print_help()
                result = -1
    except AssertionError as err:
        print('AssertionError: ' + str(err))
        result = -1

    return result


if __name__ == "__main__":
    main()
