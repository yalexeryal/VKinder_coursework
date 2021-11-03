import re
import time

from random import randrange
from datetime import datetime, timedelta

import vk_api
from vk_api.exceptions import ApiError
from vk_api.longpoll import VkLongPoll


def _get_link(id):
    return f'vk.com/id{id}'


class Vkinder_Bot:
    vk_session = None
    vk = None
    longpoll = None
    vk_user_token = None
    group_id = None

    def __init__(self, group_token, user_token):
        self.vk_session = vk_api.VkApi(token=group_token)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)
        self.vk_user_token = vk_api.VkApi(token=user_token).get_api()
        self.group_id = self.vk.groups.getById()[0]['id']

    def send_msg(self, user_id, message='.', keyboard=None, attachment=''):
        self.vk_session.method('messages.send',
                               {'user_id': user_id,
                                'message': message,
                                'keyboard': keyboard,
                                'attachment': attachment,
                                'random_id': randrange(10 ** 7), })

    def get_user_info(self, user_id):
        info = self.vk.users.get(user_ids=(user_id),
                                 fields=('first_name', 'last_name',
                                         'bdate', 'city', 'relation', 'sex'))
        return info[0]

    def get_city_id(self, city_name):
        response = self.vk_user_token.database.getCities(
            country_id=1, q=city_name)
        if len(response['items']) > 0:
            return response['items'][0]['id']
        else:
            return None

    @classmethod
    def _get_search_exec_code(cls, params, count=100):
        code = f"""var users = [];
               var offset = 0;
               while (offset < 1000) {{
                    var resp = API.users.search(
                                {{\"city\": {params['city']},
                                \"count\": {count},
                                \"offset\": offset,
                                \"sex\": {params['gender']},
                                \"status\": {params['status']},
                                \"birth_year\": {params['b_year']},
                                \"fields\": (\"last_seen\")}});
                    if (resp[\"count\"] > 1000) {{
                        return resp;}};
                    users.push(resp[\"items\"]);
                    offset = offset + {count};
               }};
               return users;
        """

        return code

    @classmethod
    def _get_search_exec_code_months(cls, params, count=1000):
        code = f"""var month = 1;
                users = [];
                big_months = [];
                while (month < 13) {{
                    response = API.users.search(
                                        {{\"city\": {params['city']},
                                        \"count\": {count},
                                        \"sex\": {params['gender']},
                                        \"status\": {params['status']},
                                        \"birth_year\":{params['b_year']},
                                        \"birth_month\": month,
                                        \"fields\": (\"last_seen\")}});
                    if (response[\"count\"] > 1000) {{
                        big_months.push(month); }}
                    else {{
                        users.push(response[\"items\"]);}};
                    month = month + 1;
                }};
                return {{\"users\": users, \"months\": big_months}};
        """

        return code

    @classmethod
    def _get_search_exec_code_days(cls, params, d_from,
                                   d_to, count=1000, month=0):
        code = f"""var month = {month};
                day = {d_from};
                users = [];
                while (day < {d_to} + 1) {{
                    response = API.users.search(
                                    {{\"city\": {params['city']},
                                    \"count\": {count},
                                    \"sex\": {params['gender']},
                                    \"status\": {params['status']},
                                    \"birth_year\": {params['b_year']},
                                    \"birth_month\": month,
                                    \"fields\": (\"last_seen\"),
                                    \"birth_day\": day}});
                    users.push(response[\"items\"]);
                    day = day + 1;
                }};
                return users;
                """

        return code

    @classmethod
    def get_last_seen(cls, users_list):
        last_online_time = time.mktime((datetime.now() -
                                        timedelta(days=7)).timetuple())
        last_online_ids = []
        for user in users_list:
            if 'last_seen' in user \
                    and user['last_seen']['time'] >= last_online_time:
                last_online_ids.append(user['id'])
        return last_online_ids

    def search_all_users(self, params):
        users = []
        response = self.vk_user_token.execute(
            code=self._get_search_exec_code(params))
        if 'count' not in response:
            [users.extend(i) for i in response]
            return self.get_last_seen(users)

        response = self.vk_user_token.execute(
            code=self._get_search_exec_code_months(params))

        [users.extend(i) for i in response['users']]
        for month in response['months']:
            response_days = self.vk_user_token.execute(
                code=self._get_search_exec_code_days(params, d_from=1,
                                                     d_to=15, month=month))
            [users.extend(i) for i in response_days]

            response_days = self.vk_user_token.execute(
                code=self._get_search_exec_code_days(params, d_from=15,
                                                     d_to=31, month=month))
            [users.extend(i) for i in response_days]

        return self.get_last_seen(users)

    def _get_photos(self, user_id, album_id=-6, offset=0):
        response = self.vk_user_token.photos.get(
            owner_id=user_id,
            extended=1,
            count=100,
            offset=offset,
            album_id=album_id
        )
        return response

    def get_most_popular_photo(self, user_id):
        response = self._get_photos(user_id)
        photos = []
        counter = 0
        offset = 0
        while response['items']:
            for photo in response['items']:
                cur_photo = {
                    'id': photo['id'],
                    'owner_id': photo['owner_id'],
                }

                count_comment = 0
                try:
                    count_comment = self.vk_user_token.photos.getComments(
                        owner_id=photo['owner_id'],
                        photo_id=photo['id']
                    )['count']
                    counter += 1
                except ApiError as msg:
                    print(msg)

                cur_photo['popularity'] = \
                    photo['likes']['count'] + count_comment
                photos.append(cur_photo)
            offset += 100
            response = self._get_photos(user_id, offset=offset)
        photos = sorted(photos, key=lambda i: i['popularity'])
        return photos[-3:]

    def get_photos_msg(self, user_id, searched_id):
        message = f'{_get_link(searched_id)}'
        attach = ''
        try:
            photos = self.get_most_popular_photo(searched_id)
            for photo in photos:
                attach += f'photo{photo["owner_id"]}_{photo["id"]},'

        except ApiError as msg:
            print(msg)

        return {'msg': message, 'attach': attach}

    def get_last_searched_from_msg(self, user_id):
        msg_history = self.vk.messages.getHistory(user_id=user_id, count=200)
        for msg in msg_history['items']:
            if msg['from_id'] == -self.group_id:
                if re.search(r'vk.com/id[0-9]{1-9}', msg['text']):
                    id = re.search('[0-9]{1-9}', msg['text'])[0]
                    return id
        return None
