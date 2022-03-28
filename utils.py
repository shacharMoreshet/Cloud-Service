import os


class Action:
    def __init__(self, action_type, path, folder_path, rename_to=''):
        self.action_type = action_type
        self.path = path
        self.folder_path = folder_path
        self.rename_to = rename_to

    def __str__(self):
        return self.action_type + os.path.relpath(self.path, self.folder_path) + (
            '' if self.rename_to == '' else Def.new_name_prefix + os.path.relpath(self.rename_to, self.folder_path))


class Def:  # cases of client's message content
    NEXT_MSG = "next"
    RECEIVE_SIZE = 1000  # Size of data to read from buffer.

    # watchdog updates prefixes:
    create_dir_prefix = 'CD;'
    delete_dir_prefix = 'DD;'
    rename_file_or_dir_prefix = 'RFD;'
    update_dir_prefix = 'MD;'
    create_file_prefix = 'CF;'
    delete_file_prefix = 'DF;'
    update_file_prefix = 'UF;'
    new_name_prefix = ';NN;'

    # server request cases:
    NEW_COMPUTER = 1
    NEW_UPDATES = 2  # case need to update files
    EXISTING_COMPUTER = 3
    NEW_CLIENT = 4

    # header's parts names
    class H:
        CHOICE = 0
        SERIAL = 1
        COMPUTER_ID = 2
        PATH = 3


# send a file to the server
# get path - the complete path in sender's computer.
# get also (FOLDER_PATH) the main folder location in sender's computer, to compute the local path
def send_file_with_action(s, action):
    send_file(s, action.__str__(), action.path)


def send_file(s, action_string, filepath):
    f = open(filepath, 'rb')
    s.send(action_string.encode('utf-8'))
    # first message with info like file name, before sending the file
    s.recv(1024)
    chunk = f.read(1024)

    if chunk:
        while chunk:
            s.send(chunk)
            chunk = f.read(1024)
    else:
        s.send('empty'.encode('utf-8'))
    f.close()


# send_all_files() get as arguments: 1. socket of sender. 2.folder_path of main-folder of sender
def send_all_files(socket, folder_path):
    has_sent_root = False
    for (path, dirs, files) in os.walk(folder_path, topdown=True):
        # send directories
        relative_path = os.path.relpath(path, folder_path)
        for file in files:
            # Check if we are at the first level of the directory or in a nested folder
            file_path = os.path.join(folder_path, file) if relative_path == '.' else os.path.join(folder_path,
                                                                                                  relative_path, file)
            send_file_with_action(socket, Action(Def.create_file_prefix, file_path, folder_path))
            socket.recv(1024)
        for dir in dirs:
            # Check if we are at the first level of the directory or in a nested folder
            dir_name = dir if relative_path == '.' else os.path.join(relative_path, dir)
            socket.send((Def.create_dir_prefix + dir_name).encode('utf-8'))
            socket.recv(1024)
            for file in files:
                file_path = os.path.join(folder_path, file) if relative_path == '.' else os.path.join(folder_path,
                                                                                                      relative_path,
                                                                                                      file)
                send_file_with_action(socket, Action(Def.create_file_prefix, file_path, folder_path))
                socket.recv(1024)
    socket.send("sent all files".encode('utf-8'))
    socket.recv(1024)


def get_all_files(s, local_path):
    final_path = local_path

    while True:
        data = s.recv(1000).decode('utf-8')
        if data == "sent all files":
            s.send(Def.NEXT_MSG.encode('utf-8'))
            # if client finished to send all files- break
            break
        update_file_or_dir(s, final_path, data)

        s.send(Def.NEXT_MSG.encode('utf-8'))


def update_file_or_dir(s, local_path, msg_data):
    if msg_data.startswith(Def.create_dir_prefix):
        dir_name = msg_data.split(Def.create_dir_prefix)[1]
        os.makedirs(os.path.join(local_path, dir_name), exist_ok=True)

    elif msg_data.startswith(Def.create_file_prefix):
        file_name = msg_data.split(Def.create_file_prefix)[1]
        s.send(Def.NEXT_MSG.encode('utf-8'))
        write_file(os.path.join(local_path, file_name), s)

    elif msg_data.startswith(Def.delete_dir_prefix):
        dir_name = msg_data.split(Def.delete_dir_prefix)[1]
        path = os.path.join(local_path, dir_name)
        delete_dir(path)

    elif msg_data.startswith(Def.delete_file_prefix):
        file_name = msg_data.split(Def.delete_file_prefix)[1]
        path = os.path.join(local_path, file_name)
        if os.path.exists(path):
            os.remove(path)

    elif msg_data.startswith(Def.update_file_prefix):
        file_name = msg_data.split(Def.update_file_prefix)[1]
        s.send(Def.NEXT_MSG.encode('utf-8'))
        path = os.path.join(local_path, file_name)
        if os.path.exists(path):
            os.remove(path)
            write_file(os.path.join(local_path, file_name), s)

    elif msg_data.startswith(Def.rename_file_or_dir_prefix):
        action_data = msg_data.split(Def.rename_file_or_dir_prefix)[1].split(Def.new_name_prefix);
        file_or_dir = os.path.join(local_path,
                                   action_data[0])
        new_file_or_dir = os.path.join(local_path,
                                       action_data[1])
        # This condition is important because WatchDog triggers the rename event for all the files/dirs under the
        # current dir
        if os.path.exists(os.path.dirname(new_file_or_dir)) and os.path.exists(file_or_dir):
            os.replace(file_or_dir, new_file_or_dir)


def delete_dir(path):
    if os.path.exists(path):
        for the_file in os.listdir(path):
            file_path = os.path.join(path, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                else:
                    delete_dir(file_path)
                    os.rmdir(file_path)
            except Exception as e:
                print(e)
        os.rmdir(path)


def write_file(file_path, socket):
    with open(file_path, 'wb') as f:
        flag = True
        while flag:
            data = socket.recv(1024)

            # This check is only relevant to txt files
            if '.txt' in os.path.basename(file_path) and data.decode('utf-8') == 'empty':
                break

            if len(data) < 1024:
                flag = False

            if not data:
                break
            # write data to a file
            f.write(data)
    f.close()


# simplify the reading of the header
# returns the given part of the header. f.e: 0 returns the choice
def read_header(header, part):
    if part == Def.H.CHOICE:  # choice
        return int.from_bytes(header[:4], byteorder='little')
    elif part == Def.H.SERIAL:  # serial
        return header[4:132].decode("utf-8")
    elif part == Def.H.COMPUTER_ID:  # computer_id
        return int.from_bytes(header[132:136], byteorder='little')
    elif part == Def.H.PATH:  # path
        return header[136:].decode("utf-8")
