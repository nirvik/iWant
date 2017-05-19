import json
from functools import wraps
import time_uuid
from constants import INDEXED, LEADER_NOT_READY,\
    ERROR_LIST_ALL_FILES, LEADER,\
    HASH_DUMP, FILE_SYS_EVENT, SEARCH_REQ, SEARCH_RES, \
    LOOKUP, IWANT_PEER_FILE, PEER_LOOKUP_RESPONSE,\
    SEND_PEER_DETAILS, FILE_DETAILS_RESP, INIT_FILE_REQ, \
    FILE_TO_BE_DOWNLOADED, DEAD,\
    NEW_PEER, BCAST_LEDGER, NEW_LEADER, REMOVE_LEADER, \
    SECRET_VAL, HANDLE_PONG, FACE_OFF,\
    RE_ELECTION, ALIVE, HANDLE_ALIVE,\
    HANDLE_PING, REQ_CHUNK, END_GAME, FILE_CONFIRMATION_MESSAGE,\
    INTERESTED, UNCHOKE, PEER_DEAD, CHANGE, SHARE, NEW_DOWNLOAD_FOLDER_RES,\
    NEW_SHARED_FOLDER_RES, HASH_IDENTITY_RESPONSE, GET_HASH_IDENTITY, HASH_NOT_PRESENT


def finishing(func):
    @wraps(func)
    def jsonify(key, **kwargs):
        _EOL = '\r'
        return json.dumps(func(key, **kwargs)) + _EOL
    return jsonify


@finishing
def bake(key, **kwargs):
    '''
        This utility is for crafting `action messages` to be sent across the network.
        The `action_msg` contains `type` and `payload`
    '''
    action_msg = {}
    action_msg['type'] = key
    action_msg['payload'] = None
    payload = {}

    def _craft_new_peer_msg():
        # print NEW_PEER, kwargs
        try:
            payload['identity'] = kwargs['identity'].hex
        except:
            payload['identity'] = None
        try:
            payload['leader_id'] = kwargs['leader_id'].hex
        except:
            payload['leader_id'] = None
        action_msg['payload'] = payload
        return action_msg

    def _craft_remove_leader_msg():
        # print REMOVE_LEADER
        payload['leader_id'] = kwargs['leader_id'].hex
        action_msg['payload'] = payload
        return action_msg

    def _craft_re_election_msg():
        # print RE_ELECTION
        payload['election_id'] = kwargs['election_id']
        action_msg['payload'] = payload
        return action_msg

    def _craft_handle_pong_msg():
        # print HANDLE_PONG
        payload['secret_value'] = kwargs['secret_value']
        action_msg['payload'] = payload
        return action_msg

    def _craft_new_leader_msg():
        # print NEW_LEADER
        payload['leader_id'] = kwargs['leader_id'].hex
        payload['election_id'] = kwargs['election_id']
        payload['secret_value'] = kwargs['secret_value']
        action_msg['payload'] = payload
        return action_msg

    def _craft_alive_msg():
        # print ALIVE
        payload['election_id'] = kwargs['election_id']
        action_msg['payload'] = payload
        return action_msg

    def _craft_handle_alive_msg():
        # print HANDLE_ALIVE
        payload['election_id'] = kwargs['election_id']
        action_msg['payload'] = payload
        return action_msg

    def _craft_handle_ping_msg():
        payload['ping'] = kwargs['ping']
        action_msg['payload'] = payload
        return action_msg

    def _craft_bcast_ledger_msg():
        try:
            payload['leader_id'] = kwargs['leader_id'].hex
        except AttributeError:
            payload['leader_id'] = None
        ledger = {}
        for uuid, value in kwargs['ledger'].iteritems():
            ledger[uuid.hex] = value
        payload['ledger'] = ledger
        payload['secret_value'] = kwargs['secret_value']
        action_msg['payload'] = payload
        return action_msg

    def _craft_secret_val_msg():
        # print SECRET_VAL
        payload['secret_value'] = kwargs['secret_value']
        action_msg['payload'] = payload
        return action_msg

    def _craft_face_off_msg():
        # print FACE_OFF
        payload['with_leader'] = kwargs['with_leader']
        action_msg['payload'] = payload
        return action_msg

    def _craft_dead_msg():
        try:
            payload['dead_uuid'] = kwargs['dead_uuid'].hex
        except AttributeError:
            payload['dead_uuid'] = None
        payload['secret_value'] = kwargs['secret_value']
        action_msg['payload'] = payload
        return action_msg

    # SERVER MESSAGES
    def _craft_unchoke_msg():
        payload['unchoke'] = kwargs['unchoke']
        action_msg['payload'] = payload
        return action_msg

    def _craft_error_list_all_files_msg():
        payload['reason'] = kwargs['reason']
        action_msg['payload'] = payload
        return action_msg

    def _craft_leader_not_ready_msg():
        payload['reason'] = kwargs['reason']
        action_msg['payload'] = payload
        return action_msg

    def _craft_search_response_msg():
        payload['search_query_response'] = kwargs['search_query_response']
        action_msg['payload'] = payload
        return action_msg

    def _craft_peer_lookup_response_msg():
        payload['peer_lookup_response'] = kwargs['peer_lookup_response']
        action_msg['payload'] = payload
        return action_msg

    def _craft_hash_dump_msg():
        payload['identity'] = kwargs['identity'].hex
        payload['operation'] = kwargs['operation']
        action_msg['payload'] = payload
        return action_msg

    def _craft_init_file_req_msg():
        payload['filehash'] = kwargs['filehash']
        action_msg['payload'] = payload
        return action_msg

    def _craft_leader_msg():
        payload['leader'] = kwargs['leader']
        action_msg['payload'] = payload
        return action_msg

    def _craft_peer_dead_msg():
        try:
            payload['dead_uuid'] = kwargs['dead_uuid'].hex
        except AttributeError:
            payload['dead_uuid'] = None
        action_msg['payload'] = payload
        return action_msg

    def _craft_file_sys_event_msg():
        payload['ADD'] = kwargs['ADD']
        payload['DEL'] = kwargs['DEL']
        payload['shared_folder'] = kwargs['shared_folder']
        action_msg['payload'] = payload
        return action_msg

    def _craft_search_req_msg():
        payload['search_query'] = kwargs['search_query']
        action_msg['payload'] = payload
        return action_msg

    def _craft_lookup_msg():
        payload['search_query'] = kwargs['search_query']
        action_msg['payload'] = payload
        return action_msg

    def _craft_iwant_peer_file_msg():
        payload['filehash'] = kwargs['filehash']
        action_msg['payload'] = payload
        return action_msg

    def _craft_send_peer_details_msg():
        payload['filehash'] = kwargs['filehash']
        action_msg['payload'] = payload
        return action_msg

    def _craft_indexed_msg():
        payload['ADD'] = kwargs['ADD']
        payload['DEL'] = kwargs['DEL']
        payload['shared_folder'] = kwargs['shared_folder']
        action_msg['payload'] = payload
        return action_msg

    def _craft_req_chunk_msg():
        payload['piece_data'] = kwargs['piece_data']
        action_msg['payload'] = payload
        # print action_msg
        return action_msg

    def _craft_end_game_msg():
        payload['end_game'] = kwargs['end_game']
        action_msg['payload'] = payload
        return action_msg

    def _craft_file_details_resp():
        pass

    def _craft_file_to_be_downloaded_msg():
        # payload['filesize'] = kwargs['filesize']
        # payload['filename'] = kwargs['filename']
        payload['message'] = kwargs['message']
        action_msg['payload'] = payload
        return action_msg

    def _craft_interested_msg():
        payload['filehash'] = kwargs['filehash']
        action_msg['payload'] = payload
        return action_msg

    def _craft_file_confirmation_message():
        payload['piecehashes'] = kwargs['piecehashes']
        action_msg['payload'] = payload
        return action_msg

    def _craft_change_download_path_msg():
        payload['download_folder'] = kwargs['download_folder']
        action_msg['payload'] = payload
        return action_msg

    def _craft_share_new_folder_msg():
        payload['shared_folder'] = kwargs['shared_folder']
        action_msg['payload'] = payload
        return action_msg

    def _craft_new_download_folder_response_msg():
        payload['download_folder_response'] = kwargs[
            'download_folder_response']
        action_msg['payload'] = payload
        return action_msg

    def _craft_new_shared_folder_response_msg():
        payload['shared_folder_response'] = kwargs['shared_folder_response']
        action_msg['payload'] = payload
        return action_msg

    def _craft_get_hash_identity_msg():
        payload['checksum'] = kwargs['checksum']
        action_msg['payload'] = payload
        return action_msg

    def _craft_hash_identity_response_msg():
        payload['file_structure_response'] = kwargs['file_structure_response']
        action_msg['payload'] = payload
        return action_msg

    def _craft_hash_not_present_msg():
        payload['reason'] = kwargs['reason']
        action_msg['payload'] = payload
        return action_msg

    dispatcher = {
        NEW_PEER: _craft_new_peer_msg,
        REMOVE_LEADER: _craft_remove_leader_msg,
        RE_ELECTION: _craft_re_election_msg,
        HANDLE_PONG: _craft_handle_pong_msg,
        NEW_LEADER: _craft_new_leader_msg,
        ALIVE: _craft_alive_msg,
        HANDLE_PING: _craft_handle_ping_msg,
        HANDLE_ALIVE: _craft_handle_alive_msg,
        BCAST_LEDGER: _craft_bcast_ledger_msg,
        SECRET_VAL: _craft_secret_val_msg,
        FACE_OFF: _craft_face_off_msg,
        DEAD: _craft_dead_msg,

        UNCHOKE: _craft_unchoke_msg,
        ERROR_LIST_ALL_FILES: _craft_error_list_all_files_msg,
        LEADER_NOT_READY: _craft_leader_not_ready_msg,
        SEARCH_RES: _craft_search_response_msg,
        HASH_DUMP: _craft_hash_dump_msg,
        INIT_FILE_REQ: _craft_init_file_req_msg,
        LEADER: _craft_leader_msg,
        PEER_DEAD: _craft_peer_dead_msg,
        FILE_SYS_EVENT: _craft_file_sys_event_msg,
        SEARCH_REQ: _craft_search_req_msg,
        LOOKUP: _craft_lookup_msg,
        IWANT_PEER_FILE: _craft_iwant_peer_file_msg,
        SEND_PEER_DETAILS: _craft_send_peer_details_msg,
        PEER_LOOKUP_RESPONSE: _craft_peer_lookup_response_msg,
        INDEXED: _craft_indexed_msg,
        REQ_CHUNK: _craft_req_chunk_msg,
        END_GAME: _craft_end_game_msg,
        INTERESTED: _craft_interested_msg,
        FILE_DETAILS_RESP: _craft_file_details_resp,
        FILE_CONFIRMATION_MESSAGE: _craft_file_confirmation_message,
        FILE_TO_BE_DOWNLOADED: _craft_file_to_be_downloaded_msg,

        CHANGE: _craft_change_download_path_msg,
        SHARE: _craft_share_new_folder_msg,
        NEW_DOWNLOAD_FOLDER_RES: _craft_new_download_folder_response_msg,
        NEW_SHARED_FOLDER_RES: _craft_new_shared_folder_response_msg,

        GET_HASH_IDENTITY: _craft_get_hash_identity_msg,
        HASH_IDENTITY_RESPONSE: _craft_hash_identity_response_msg,
        HASH_NOT_PRESENT: _craft_hash_not_present_msg
    }
    return dispatcher[key]()


def unbake(message=None):
    json_msg = json.loads(message)
    if 'leader_id' in json_msg['payload']:
        leader_uuid = json_msg['payload']['leader_id']
        if leader_uuid is not None:
            json_msg['payload']['leader_id'] = time_uuid.TimeUUID(leader_uuid)

    if 'identity' in json_msg['payload']:
        identity_uuid = json_msg['payload']['identity']
        if identity_uuid is not None:
            json_msg['payload']['identity'] = time_uuid.TimeUUID(identity_uuid)

    if 'dead_uuid' in json_msg['payload']:
        dead_uuid = json_msg['payload']['dead_uuid']
        if dead_uuid is not None:
            json_msg['payload']['dead_uuid'] = time_uuid.TimeUUID(dead_uuid)

    if 'ledger' in json_msg['payload']:
        ledger = {}
        ledger_response = json_msg['payload']['ledger']
        if ledger_response:
            for uuid, values in ledger_response.iteritems():
                ledger[time_uuid.TimeUUID(uuid)] = values
        json_msg['payload']['ledger'] = ledger

    action_dispatcher, action_payload = json_msg['type'], json_msg['payload']
    return action_dispatcher, action_payload
