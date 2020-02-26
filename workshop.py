#!/usr/bin/python3

import sys,getopt
import os

import urllib.request, urllib.parse, urllib
from urllib.error import HTTPError, URLError
import json
import time

def safe_print(*objects, errors = 'ignore', **kwargs):
    '''
    I really don't want to have to bother with fixing up all my texts when printing, so here's
    an ascii-only print function
    '''
    print( *(str(t).encode('ascii', errors = errors).decode('ascii') for t in objects), **kwargs)


def usage(cmd, exit):
    print ("usage: " + cmd + "[-o <output_dir>] [<collection_id>]..." \
            "<collection_id>")
    sys.exit(exit)

const_urls = {
        'file' : "http://api.steampowered.com/ISteamRemoteStorage/" \
                "GetPublishedFileDetails/v1",
        'collection' : "http://api.steampowered.com/ISteamRemoteStorage/" \
                "GetCollectionDetails/v0001"
        }
const_data = {
        'file' : {'itemcount' : 0, 'publishedfileids[0]' : 0},
        'collection' : {'collectioncount' : 0, 'publishedfileids[0]' : 0}
        }

def download_plugins (output_dir, plugins, old_plugins):
    """Download only plugin that are not up-to-date or never downloaded
    Will return:
        - the number of error uncounter
        - an array of plugins that failed to download
        - a dictionnay of plugins that succeed to download with plugin id as
            key and only the title and time_updaed filed
    Return int(error), array(failed_plugins), dict(succeed_plugins)
    """
    fail = []
    succeed = dict()
    error = 0
    for plugin in plugins:
        if 'file_url' in plugin:
            plugin_display_name = '"{title}" ({publishedfileid}.vpk)'.format(**plugin)
            # if plugin is downloadable
            if plugin['publishedfileid'] in old_plugins and \
            old_plugins[plugin['publishedfileid']]['time_updated'] == \
            plugin['time_updated']:
                # if plugin is already up-to-date just reccord as succeed
                safe_print("Plugin " + plugin_display_name + \
                        " already up-to-date")
                succeed[plugin['publishedfileid']] = dict((k,plugin[k]) \
                    for k in ('title', 'time_updated') \
                    if k in plugin)
            else:
                # if plugin not up-to-date or never download
                try:
                    name = plugin['publishedfileid'] + ".vpk"
                    safe_print("Downloading " + plugin_display_name)
                    path = os.path.join(output_dir, name)
                    urllib.request.urlretrieve(plugin['file_url'], path)
                    print("Downloading complete")
                    succeed[plugin['publishedfileid']] = dict((k,plugin[k]) \
                        for k in ('title', 'time_updated') \
                        if k in plugin)
                except HTTPError as e:
                    # some time the request fail, too much spam ?
                    safe_print("Server return " + str(e.code) + " error on " + \
                        plugin_display_name)
                    fail.append(plugin)
                    error += 1
    return error, fail, succeed

def get_plugins_info (plugins_id_list):
    """Ask api the info on each plugin(s)
    Will return:
        - error:
            - None if no error encounter
            - the error an error occur
        - an array of plugin with the all the data return by the steam api
    Return error(error), array(array_of_plugins)
    """
    json_response = []
    error = None
    data = const_data['file']
    data['itemcount'] = len(plugins_id_list)
    for idx, plugin_id in enumerate(plugins_id_list):
        data['publishedfileids[' + str(idx) + ']'] = plugin_id
    encode_data = urllib.parse.urlencode(data).encode('ascii')
    try:
        response = urllib.request.urlopen(const_urls['file'], encode_data)
    except HTTPError as e:
        print("Server return " + str(e.code) + " error")
        error = e
    except URLError as e:
        print("Can't reach server: " + e.reason)
        error = e
    else:
        json_response = json.loads(response.read().decode('utf8'))
        json_response = json_response['response']['publishedfiledetails']
    return error, json_response

def get_plugins_id_from_collections_list (collections_id_list):
    """Ask the steam api for every plugin in the collection(s) and
    subcollection(s)
    Will return:
        - error:
            - None if no error encounter
            - the error an error occur
        - an array of all plugins id
        - an array of the valid collection(s) id given as arg (and not all the
            subcollection)
    Return error(error), array(plugin_id), array(valid_collections_id)
    """
    valid_collections = []
    sub_collection = []
    plugins_id_list = []
    error = None
    data = const_data['collection']
    data['collectioncount'] = len(collections_id_list)
    for idx, collection_id in enumerate(collections_id_list):
        data['publishedfileids[' + str(idx) + ']'] = collection_id
    encode_data = urllib.parse.urlencode(data).encode('ascii')
    try:
        response = urllib.request.urlopen(const_urls['collection'], encode_data)
    except HTTPError as e:
        print("Server return " + str(e.code) + " error")
        error = e
    except URLError as e:
        print("Can't reach server: " + e.reason)
        error = e
    else:
        json_response = json.loads(response.read().decode('utf-8'))
        for collection in json_response['response']['collectiondetails']:
            if 'children' in collection:
                # if collection is a valid one
                valid_collections.append(collection['publishedfileid'])
                for item in collection['children']:
                    if item['filetype'] == 0:   # children is a plugin
                        plugins_id_list.append(item['publishedfileid'])
                    elif item['filetype'] == 2: # childre is a collection
                        sub_collection.append(item['publishedfileid'])
                    else:                       # unknown type
                        print("Unrecognised filetype: " + str(item['filetype']))
        if len(sub_collection) > 0:
            error, plugins_id_list_temp, o = \
                get_plugins_id_from_collections_list(sub_collection)
            if error == None:
                plugins_id_list += plugins_id_list_temp
    return error, plugins_id_list, valid_collections

def load_saved_data(save_file):
    """Return the saved data
    Will return:
        - a dictionnay:
            - empty if no saved data as been found
            - containing saved data if any
    Return dict(saved_data)
    """
    if os.path.isfile(save_file):
        file = open(save_file, 'r')
        saved_data = json.loads(file.read())
        file.close()
    else:
        saved_data = dict()
    return saved_data


def init(argv):
    """Read the args and return all variable
    Will return:
        - the number of error encounter
        - the absolute path of the output directory
        - an array of collection id given as args (in fact everything that is
            not a recognised arg
        - the absolute path of the save file
    Return int(error), string(output_dir), array(collections_id),
        string(save_file)
    """
    error = 0
    output_dir = os.getcwd()
    collections_id_list = []
    save_file = os.path.join(output_dir, "addons.lst")
    if len(argv) == 1 and not os.path.isfile(save_file):
        print("No save file found")
        usage(argv[0], 0)
    try:
        opts, args = getopt.getopt(argv[1:],"ho:")
    except getopt.GetoptError:
        usage(argv[0], 2)
    else:
        for opt, arg in opts:
            if opt == 'h':
                usage(argv[0], 0)
            elif opt == '-o':
                output_dir = os.path.abspath(arg)
                save_file = os.path.join(output_dir, "addons.lst")
        if not os.path.exists(output_dir):
            print(output_dir + ": path doesn't exist\nEnd of program")
            error += 1
        collections_id_list = argv[len(opts) * 2 + 1:]
    return error, output_dir, collections_id_list, save_file

"""Return list of deprecated plugins
Will return:
    - a list:
        - empty if no deprecated plugins found
        - containing deprecated plugins
Return list(deprecated_plugins)
"""
def plugins_to_remove(plugins_id_list, old_plugins):
    deprecated_plugins = []
    for plugin in old_plugins:
        if plugin not in plugins_id_list:
            deprecated_plugins.append(plugin)
    return deprecated_plugins


"""Removes old plugins and modifies list
Will return:
    - a dictionary item:
        - saved_data (without the deprecated plugins)
Return dict(deprecated_plugins)
"""
def deletePlugins(deprecated_plugins, output_dir, saved_data):
    for plugin in deprecated_plugins:
        # remove plugins from server
        plugin_path = os.path.join(output_dir, plugin + ".vpk")
        if os.path.exists(plugin_path):
            os.remove(plugin_path)
        # remove from the dictionary (addons.lst)
        del saved_data['plugins'][plugin]
    return saved_data

def print_deprecated_info(deprecated_plugin_info):
    for plugin in deprecated_plugin_info:
        if 'file_url' in plugin:
            plugin_display_name = '"{title}" ({publishedfileid}.vpk)'.format(**plugin)
            safe_print("\t" + plugin_display_name)

def main(argv):
    sleep = 15
    error, output_dir, collections_id_list, save_file = init(argv)
    if error == 0:
        saved_data = load_saved_data(save_file)
        if 'collections' in saved_data:
            if len(collections_id_list) == 0:
                collections_id_list = saved_data['collections']
            else:
                collections_id_list += saved_data['collections']
                collections_id_list = list(set(collections_id_list))
        if len(collections_id_list) == 0:
            print("No collection(s) id given and no collection(s) id found in " + save_file)
            error = 1
    if error == 0:
        error, plugins_id_list, valid_collections = get_plugins_id_from_collections_list(collections_id_list)
    if error == None:
        saved_data['collections'] = valid_collections
        if 'plugins' in saved_data:
            old_plugins = saved_data['plugins']
            
            # plugin got removed from workshop collections - delete it
            deprecated_plugins = plugins_to_remove(plugins_id_list, old_plugins)
            deprecated_plugins = list(set(deprecated_plugins))
            if len(deprecated_plugins) > 0:
                print("\nSome plugins found which are no longer in workshop collection(s).")
                print("Removing deprecated plugins:\n")
                error, deprecated_plugin_info = get_plugins_info(deprecated_plugins)
                if error == None:
                    print_deprecated_info(deprecated_plugin_info)
                    # remove plugins from server and resave dictionary to reflect change
                    saved_data = deletePlugins(deprecated_plugins, output_dir, saved_data)
                    
            plugins_id_list += old_plugins.keys()
            plugins_id_list = list(set(plugins_id_list))
        else:
            old_plugins = dict()
        saved_data['plugins'] = dict()
        error, plugins_info = get_plugins_info(plugins_id_list)
    if error == None:
        num_download_failures = 0
        print("\n")
        while len(plugins_info) > 0 and num_download_failures < 25:
            error, plugins_info, succeed_temp = download_plugins(output_dir, plugins_info, old_plugins)
            saved_data['plugins'].update(succeed_temp)
            file = open(save_file, 'w')
            file.write(json.dumps(saved_data, indent=4))
            file.close()
            if error > 0:
                print(str(len(plugins_info)) + " plugins failed to download, retrying in " + str(sleep) + " seconds")
                time.sleep(sleep)
                num_download_failures += 1
                print('--------------------------------------------------')
                print('Failed downloads (attempt #{} / 25)'.format(num_download_failures))
            else:
                # clear the counter
                num_download_failures = 0
        if num_download_failures:
            print('Gave up on downloading all plugins, blame Valve')
        else:
            print('Downloaded all plugins successfully')

if __name__ == "__main__":
    main(sys.argv)