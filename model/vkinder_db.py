import sqlalchemy as sq
from sqlalchemy.orm import Session

from database_model import User, AssotiationUser, SearchParams, Base


class Vkinder_DB:
    session = None
    engine = None
    Base = Base

    def __init__(self, connect):
        self.engine = sq.create_engine(connect)
        self.session = Session(bind=self.engine)

    def init_db(self):
        self.Base.metadata.create_all(self.engine)
        print('db_created')

    def drop_all(self):
        self.Base.metadata.drop_all(self.engine)
        print('bd was drop')

    def get_user(self, user_id):
        user = self.session.get(User, user_id)
        return user

    def add_user(self, user_id):
        new_user = User(id=user_id)
        self.session.add(new_user)
        self.session.commit()

    def set_search_params(self, user_id, search_params):
        user = self.get_user(user_id)
        if user.params:
            user.params.b_year = search_params['b_year']
            user.params.city = search_params['city']
            user.params.status = search_params['status']
            user.params.gender = search_params['gender']
        else:
            new_params = SearchParams(
                user_id=user.id,
                b_year=search_params['b_year'],
                city=search_params['city'],
                status=search_params['status'],
                gender=search_params['gender']
            )
            self.session.add(new_params)
        self.session.commit()

    def get_search_params(self, user_id):
        user = self.session.get(User, user_id)
        if not user:
            return None
        bd_params = user.params
        if bd_params:
            params = {
                'city': bd_params.city,
                'status': bd_params.status,
                'gender': bd_params.gender,
                'b_year': bd_params.b_year
            }
            return params
        else:
            return None

    def add_viewed(self, user_id, viewed_id):
        self.session.get(AssotiationUser,
                         (user_id, viewed_id)).is_viewed = True
        self.session.commit()

    def get_searched_id(self, user_id):

        searched_list = self.session.query(AssotiationUser).filter(
            AssotiationUser.user_id_from == user_id,
            AssotiationUser.is_viewed == False).all()

        if not searched_list:
            return None

        self.add_viewed(user_id, searched_list[0].user_id_to)
        return searched_list[0].user_id_to

    def add_searched_users(self, user_id, searched_list_id):

        for searched_id in searched_list_id:
            if not self.get_user(searched_id):
                self.add_user(searched_id)
            searched_user = self.session.get(AssotiationUser,
                                             (user_id, searched_id))
            if searched_user:
                searched_user.is_viewed = False
            else:
                self.session.add(AssotiationUser(user_id_from=user_id,
                                                 user_id_to=searched_id))
        self.session.commit()

    def delete_searched(self, user_id):
        searcheds = self.get_user(user_id).user_to

        for searched in searcheds:
            self.session.delete(searched)
        self.session.commit()

    def add_favourite_user(self, user_id, favorite_id):
        self.session.get(
            AssotiationUser, (user_id, favorite_id)).is_favorite = True
        self.session.commit()

    def delete_from_favourite(self, user_id, favorite_id):
        self.session.get(
            AssotiationUser, (user_id, favorite_id)).is_favorite = False
        self.session.commit()

    def get_favourite_ids(self, user_id):
        favorite_list = self.session.query(AssotiationUser).filter(
            AssotiationUser.user_id_from == user_id,
            AssotiationUser.is_favorite == True).all()
        return favorite_list
