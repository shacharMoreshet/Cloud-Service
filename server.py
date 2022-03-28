import socket
import sys
import random
import string
import os

# Size of data to read from buffer.
import utils

# #####client_id_dict########
# saves pair of serials and a dictionary of computers_ids
# the 2nd dictionary has a list of changes for every computer
client_id_dict = {}
computer_id_counter_dict = {}
current_serial = 0  # the serial of the connected client
current_computer_id = None
# handle here main args
try:
    PORT_TO_LISTEN = sys.argv[1]
except:
    exit()
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', int(PORT_TO_LISTEN)))
server.listen(100)


# create a serial for new clients
def create_serial():
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    serial_code = ''.join(random.choice(chars) for _ in range(128))
    client_socket.send(str.encode(serial_code))
    return serial_code


def get_serial_path(serial):
    script_path = os.path.abspath(__file__)
    head, file_name = os.path.split(script_path)
    return os.path.join(head, str(serial))


while True:
    client_socket, client_address = server.accept()
    req_data = client_socket.recv(utils.Def.RECEIVE_SIZE)
    request = utils.read_header(req_data, utils.Def.H.CHOICE)  # the request of user
    try:
        if request == utils.Def.NEW_CLIENT:  # converting the index of the package. 0 is new
            # client request.
            current_serial = create_serial()
            print(current_serial)
            client_socket.recv(utils.Def.RECEIVE_SIZE)
            # current_computer_id = utils.read_header(data, utils.Def.H.COMPUTER_ID)
            os.mkdir(current_serial)  # create serial folder in server's location
            # add client to the dictionary.
            client_id_dict[current_serial] = {}  # create new 2nd dict for new client
            computer_id_counter_dict[current_serial] = 0
            client_socket.send((0).to_bytes(4, 'little'))
            client_id_dict[current_serial][0] = []  # create a list of changes in 2nd dict
            try:
                utils.get_all_files(client_socket, get_serial_path(current_serial))
            except Exception as e:
                print(e)
            print("finished getting files of new client")

        elif request == utils.Def.NEW_COMPUTER:
            # client request.
            current_serial = utils.read_header(req_data, utils.Def.H.SERIAL)
            computer_id_counter_dict[current_serial] = computer_id_counter_dict[current_serial] + 1
            new_computer_id = computer_id_counter_dict[current_serial]
            client_socket.send(new_computer_id.to_bytes(4, 'little'))

            client_id_dict[current_serial][new_computer_id] = []  # create a list of changes in 2nd dict
            # send the folder that is inside serial_path

            # p = get_serial_path(current_serial)
            # list_subdirs_names = [f.name for f in os.scandir(p) if f.is_dir()]
            # path = os.path.join(get_serial_path(current_serial), list_subdirs_names[0])

            utils.send_all_files(client_socket, get_serial_path(current_serial))

        elif request == utils.Def.EXISTING_COMPUTER:
            # client request
            current_serial = utils.read_header(req_data, utils.Def.H.SERIAL)
            current_computer_id = utils.read_header(req_data, utils.Def.H.COMPUTER_ID)
            for change in client_id_dict[current_serial][current_computer_id]:
                if utils.Def.create_file_prefix in change or utils.Def.update_file_prefix in change:
                    utils.send_file(client_socket, change,
                                    os.path.join(get_serial_path(current_serial), change.split(';')[1]))
                else:
                    client_socket.send(change.encode('utf-8'))  # send a single change

                client_socket.recv(utils.Def.RECEIVE_SIZE).decode('utf-8')

            client_socket.send("finished".encode('utf-8'))
            client_id_dict[current_serial][current_computer_id] = []

        elif request == utils.Def.NEW_UPDATES:  # update the folder according to changes_dict
            current_computer_id = utils.read_header(req_data, utils.Def.H.COMPUTER_ID)
            server_path = get_serial_path(current_serial)
            client_socket.send(utils.Def.NEXT_MSG.encode('utf-8'))  # 1st next

            update_data = client_socket.recv(utils.Def.RECEIVE_SIZE).decode('utf-8')

            utils.update_file_or_dir(client_socket, server_path, update_data)
            for key in client_id_dict[current_serial]:
                if key != current_computer_id:
                    client_id_dict[current_serial][key].append(update_data)

            client_socket.send(utils.Def.NEXT_MSG.encode('utf-8'))
    except Exception as e:
        print(e)
