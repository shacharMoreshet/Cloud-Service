import socket
import sys
import os
import time
import utils

# watchdog
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

COMPUTER_ID = 1000000
changes_queue = []  # use the list as a queue, using append and pop


# creates an header. [0:4] choice. [4:132] serial. [132:136] computer_id. [132: ] path.
# use utils.read_header to read specific part of header
# choice values: 0: registration request. 1-5: watchdog notifications: 1- created. 2- deleted. 3- modified. 4- moved.
def create_header(choice, serial, comp_id, path):
    encoding = 'utf-8'  # use utf-8 encoding as in the attached file
    choice_bytes = choice.to_bytes(4, 'little')
    serial_bytes = serial.encode(encoding)
    comp_id_bytes = comp_id.to_bytes(4, 'little')
    path_bytes = path.encode(encoding)

    return choice_bytes + serial_bytes + comp_id_bytes + path_bytes


def is_file(path):
    return "." in os.path.basename(path) or os.path.isfile(path)


def on_created(event):
    if not ".goutputstream" in event.src_path:  # make sure thats not linux temp file created on file content update

        # If the basename (the last string in the path) has a ".", this means it is a file name
        if not is_file(event.src_path):
            changes_queue.append(utils.Action(utils.Def.create_dir_prefix, event.src_path, FOLDER_PATH))
        else:
            changes_queue.append(utils.Action(utils.Def.create_file_prefix, event.src_path, FOLDER_PATH))


def on_deleted(event):
    if not ".goutputstream" in event.src_path:  # make sure thats not linux temp file created on file content update
        if not is_file(event.src_path):
            changes_queue.append(utils.Action(utils.Def.delete_dir_prefix, event.src_path, FOLDER_PATH))
        else:
            changes_queue.append(utils.Action(utils.Def.delete_file_prefix, event.src_path, FOLDER_PATH))


def on_modified(event):
    if not ".goutputstream" in event.src_path:  # make sure thats not linux temp file created on file content update
        if is_file(event.src_path):
            changes_queue.append(utils.Action(utils.Def.update_file_prefix, event.src_path, FOLDER_PATH))


# For some reason this is the event for file rename that Watchdog triggers
def on_moved(event):
    if not "goutputstream" in os.path.basename(event.src_path):
        changes_queue.append(
            utils.Action(utils.Def.rename_file_or_dir_prefix, event.src_path, FOLDER_PATH, event.dest_path))
    elif not "goutputstream" in os.path.basename(event.dest_path):
        changes_queue.append(utils.Action(utils.Def.update_file_prefix, event.dest_path, FOLDER_PATH))


def get_updates():
    black_list = []
    update_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    update_socket.connect_ex((SERVER_IP, SERVER_PORT))  # used _ex to prevent async errors
    update_socket.send(create_header(utils.Def.EXISTING_COMPUTER, SERIAL_CODE, COMPUTER_ID, FOLDER_PATH))
    flag = True
    while flag:
        msg_data = update_socket.recv(utils.Def.RECEIVE_SIZE).decode('utf-8')
        if msg_data == 'finished':
            flag = False
        else:
            black_list.append(msg_data)
            utils.update_file_or_dir(update_socket, FOLDER_PATH, msg_data)
            update_socket.send(utils.Def.NEXT_MSG.encode('utf-8'))

    update_socket.close()
    return black_list


def check_delete_create(change_action, black_list):
    update_action = utils.Action(utils.Def.update_file_prefix, change_action.path, FOLDER_PATH).__str__()
    if update_action in black_list:
        if change_action.action_type == utils.Def.create_file_prefix or change_action.action_type == utils.Def.delete_file_prefix:
            return False
        else:
            return True

    else:
        return True


def start_watchdog(waiting_time):
    # watchdog
    event_handler = PatternMatchingEventHandler("[*]")
    # override event_handler's methods
    event_handler.on_created = on_created
    event_handler.on_deleted = on_deleted
    event_handler.on_modified = on_modified
    event_handler.on_moved = on_moved

    observer = Observer()
    observer.schedule(event_handler, FOLDER_PATH, recursive=True)
    observer.start()
    while True:
        try:
            black_list = get_updates()
            for c in changes_queue:
                if c.__str__() not in black_list and check_delete_create(c, black_list):
                    curr_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    curr_socket.connect_ex((SERVER_IP, SERVER_PORT))  # used _ex to prevent async errors
                    head, path = os.path.split(FOLDER_PATH)  # send the path in the header
                    curr_socket.send(create_header(utils.Def.NEW_UPDATES, str(SERIAL_CODE), COMPUTER_ID, FOLDER_PATH))
                    curr_socket.recv(utils.Def.RECEIVE_SIZE)  # 1st next
                    if c.action_type == utils.Def.create_file_prefix or c.action_type == utils.Def.update_file_prefix:
                        utils.send_file_with_action(curr_socket, c)
                    else:
                        curr_socket.send(c.__str__().encode('utf-8'))  # send a single change

                    curr_socket.recv(utils.Def.RECEIVE_SIZE)
                    curr_socket.close()
            changes_queue.clear()
        except Exception as e:
            print(e)

        time.sleep(waiting_time)

    # watchdog
    observer.stop()
    observer.join()


# handle here main args
try:
    SERVER_IP = sys.argv[1]
    SERVER_PORT = int(sys.argv[2])
    FOLDER_PATH = sys.argv[3]
    WAIT_REFRESH_TIME = int(sys.argv[4])  # time to wait between sending changes to server
except:
    exit()

# create socket for first connection
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((SERVER_IP, SERVER_PORT))

# get the fifth arg - the serial. if not given - get new one from server
try:
    # NEW_COMPUTER case
    SERIAL_CODE = sys.argv[5]
    os.mkdir(FOLDER_PATH)
    s.send(create_header(utils.Def.NEW_COMPUTER, SERIAL_CODE, COMPUTER_ID, FOLDER_PATH))
    COMPUTER_ID = int.from_bytes(s.recv(utils.Def.RECEIVE_SIZE), 'little')
    # check that the serial code is long enough
    if len(SERIAL_CODE) < 128:
        exit()
    try:
        utils.get_all_files(s, FOLDER_PATH)
    except Exception as e:
        print(e)
except:
    # NEW_CLIENT case
    # send registration request to server and save the serial code
    s.send(create_header(utils.Def.NEW_CLIENT, '', COMPUTER_ID, FOLDER_PATH))
    SERIAL_CODE = s.recv(utils.Def.RECEIVE_SIZE).decode('utf-8')
    s.send('ok'.encode('utf-8'))
    COMPUTER_ID = int.from_bytes(s.recv(utils.Def.RECEIVE_SIZE), 'little')
    utils.send_all_files(s, FOLDER_PATH)

s.close()
# watchdog
start_watchdog(WAIT_REFRESH_TIME)
