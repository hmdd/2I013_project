# -*- coding: utf-8 -*-<
from functools import total_ordering
import math
import threading
from collections import namedtuple
from threading import Lock
from copy import deepcopy
from utils import Vector2D, MobileMixin, SoccerEvents, DecodeException
import settings
import random
import time

###############################################################################
# SoccerAction
###############################################################################


class SoccerAction(object):
    """ Action d'un joueur : comporte un vecteur acceleration et un vecteur shoot.
    """
    def __init__(self, acceleration=Vector2D(), shoot=Vector2D()):
        self.acceleration = acceleration
        self.shoot = shoot

    def copy(self):
        return deepcopy(self)

    def to_str(self):
        return "%s%s" % (self.acceleration, self.shoot)

    @classmethod
    def from_str(cls, strg):
        tmp = Vector2D.from_list_str(strg)
        return cls(tmp[0], tmp[1])

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return (other.acceleration == self.acceleration) and (other.shoot == self.shoot)

    def __add__(self, other):
        return SoccerAction(self.acceleration + other.acceleration, self.shoot + other.shoot)

    def __sub__(self, other):
        return Vector2D(self.acceleration - other.acceleration, self.shoot - other.shoot)

    def __iadd__(self, other):
        self.acceleration += other.acceleration
        self.shoot += other.shoot
        return self

    def __isub__(self, other):
        self.acceleration -= other.acceleration
        self.shoot -= other.shoot
        return self



##############################################################################
# SoccerStrategy
##############################################################################

class AbstractStrategy:
    """ Strategie : la fonction compute_strategie est interroge a chaque tour de jeu, elle doit retourner un objet
    SoccerAction
    """
    def __init__(self, name):
        """
        :param name: nom de la strategie
        :return:
        """
        self.name = name

    def compute_strategy(self, state, id_team, id_player):
        """ Fonction a implementer pour toute strategie
        :param state: un objet SoccerState
        :param id_team: 1 ou 2
        :param id_player: numero du joueur interroge
        :return:
        """
        return SoccerAction()

    def begin_match(self, team1, team2, state):
        """  est appelee en debut de chaque match
        :param team1: nom team1
        :param team2: nom team2
        :param state: etat initial
        :return:
        """
        pass

    def begin_round(self, team1, team2, state):
        """ est appelee au debut de chaque coup d'envoi
        :param team1: nom team 1
        :param team2: nom team 2
        :param state: etat initial
        :return:
        """
        pass

    def end_round(self, team1, team2, state):
        """ est appelee a chaque but ou fin de match
        :param team1: nom team1
        :param team2: nom team2
        :param state: etat initial
        :return:
        """
        pass

    def update_round(self, team1, team2, state):
        """ est appelee a chaque tour de jeu
        :param team1: nom team 1
        :param team2: nom team 2
        :param state: etat courant
        :return:
        """
        pass

    def end_match(self, team1, team2, state):
        """ est appelee a la fin du match
        :param team1: nom team 1
        :param team2: nom team 2
        :param state: etat courant
        :return:
        """
        pass

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


###############################################################################
# Configuration
#########################    e######################################################

class Configuration(object):
    """ Represente la configuration d'un joueur : un etat  mobile (position, vitesse), et une action SoccerAction
    """
    def __init__(self, **kwargs):
        """
        :param state: etat MobileMixin du joueur
        ;param action: action SoccerAction du joueur
        :return:
        """
        self._state = kwargs.pop('state', MobileMixin())
        self._action = kwargs.pop('action', SoccerAction())
        self._last_shoot = kwargs.pop('last_shoot', 0)
        self.__dict__.update(kwargs)

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return self.to_str()

    @property
    def position(self):
        """
        :return: Vector2D position du joueur
        """
        return self._state.position.copy()

    @property
    def vitesse(self):
        """
        :return: Vector2D vitesse du joueur
        """
        return self._state.vitesse.norm_max(settings.maxPlayerSpeed)

    @property
    def acceleration(self):
        """
        :return: Vector2D Action acceleration du joueur
        """
        return self._action.acceleration.norm_max(settings.maxPlayerAcceleration)

    @property
    def shoot(self):
        """ Vector2D Action shoot du joueur
        :return:
        """
        return self._action.shoot.norm_max(settings.maxPlayerShoot)

    @property
    def state(self):
        """
        :return: etat MobileMixin du joueur
        """
        return self._state

    @property
    def action(self):
        """
        :return: action SoccerAction du joueur
        """
        return self._action

    def next(self, ball, action):
        """ Calcul le prochain etat en fonction de l'action et de la position de la balle
        :param ball:
        :param action:
        :return: Action shoot effectue
        """
        self._action = action.copy()
        self._state.vitesse *= (1 - settings.playerBrackConstant)
        self._state.vitesse = (self._state.vitesse+self.acceleration).norm_max(settings.maxPlayerSpeed)
        self._state.position += self.vitesse
        if self._state.position.x < 0 or self.position.x > settings.GAME_WIDTH \
                or self.position.y < 0 or self.position.y > settings.GAME_HEIGHT:
            self._state.position.x = max(0, min(settings.GAME_WIDTH, self.position.x))
            self._state.position.y = max(0, min(settings.GAME_HEIGHT, self.position.y))
            self._state.vitesse.norm = 0
        if self._action.shoot.norm == 0 or not self.can_shoot():
            self._dec_shoot()
            return Vector2D()
        self._reset_shoot()
        if self._state.position.distance(ball.position) > (settings.PLAYER_RADIUS + settings.BALL_RADIUS):
            return Vector2D()
        angle_factor = 1. - abs(math.cos((self.vitesse.angle - self.shoot.angle) / 2.))
        dist_factor = 1. - self._state.position.distance(ball.position) / (
            settings.PLAYER_RADIUS + settings.BALL_RADIUS)
        shoot = self.shoot * (1 - angle_factor * 0.25 - dist_factor * 0.25)
        shoot.angle = shoot.angle + (2 * random.random() - 1.) * (
            angle_factor + dist_factor) / 2. * settings.shootRandomAngle * math.pi / 2.
        self._action = SoccerAction()
        return shoot

    def can_shoot(self):
        """ Le joueur peut-il shooter
        :return:
        """
        return self._last_shoot <= 0

    def _dec_shoot(self):
        self._last_shoot -= 1

    def _reset_shoot(self):
        self._last_shoot = settings.nbWithoutShoot

    def copy(self):
        return deepcopy(self)

    def to_str(self):
        return "%s%s" % (self.state, self.action)

    @classmethod
    def from_str(cls, strg):
        l_vect = Vector2D.from_list_str(strg)
        if len(l_vect) != 4: raise DecodeException("Wrong format for %s : %s" % (cls, strg))
        return cls(state=MobileMixin(position=l_vect[0], vitesse=l_vect[1]),
                   action=SoccerAction(acceleration=l_vect[2], shoot=l_vect[3]))

    @classmethod
    def from_position(cls, x, y):
        return cls(state=MobileMixin(position=Vector2D(x, y)))


###############################################################################
# SoccerState
###############################################################################

class SoccerState(object):
    """ Etat d'un tour du jeu. Contient la balle (MobileMixin), l'ensemble des configurations des joueurs, le score et
    le numero de l'etat.
    """
    def __init__(self, **kwargs):
        self._configs = kwargs.pop('configs', dict())
        self._ball = kwargs.pop('ball', MobileMixin())
        self._score = kwargs.pop('score', {1: 0, 2: 0})
        self._step = kwargs.pop('step', 0)
        self._winning_team = kwargs.pop('winning_team', 0)
        self.__dict__.update(kwargs)

    @property
    def ball(self):
        """
        :return: MobileMixin de la balle
        """
        return self._ball

    @property
    def step(self):
        """
        :return: numero de l'etat courant
        """
        return self._step

    def player(self, id_team, id_player):
        """ renvoie la configuration du joueur
        :param id_team: numero de la team du joueur
        :param id_player: numero du joueur
        :return:
        """
        return self._configs[(id_team, id_player)]

    def player_state(self, id_team, id_player):
        """ renvoie la position MobileMixin du joueur
        :param id_team: numero de la team du joueur
        :param id_player:  numero du joueur
        :return: configuration du joueur
        """
        return self.player(id_team, id_player).state

    def player_action(self, id_team, id_player):
        """ renvoie l'action du joueur
        :param id_team: numero de la team du joueur
        :param id_player: numero du joueur
        :return: action du joueur
        """
        return self.player(id_team, id_player).action

    @property
    def players(self):
        """ renvoie la liste des cles des joueurs (idteam,idplayer)
        :return: liste des cles
        """
        return self._configs.keys()

    def nb_players(self, team):
        """ nombre de joueurs de la team team
        :param team: 1 ou 2
        :return:
        """
        return len([x for x in self._configs.keys() if x[0] == team])

    def get_score_team(self, idx):
        """ score de la team idx : 1 ou 2
        :param idx: numero de la team
        :return:
        """
        return self._score[idx]

    @property
    def score_team1(self):
        return self.get_score_team(1)

    @property
    def score_team2(self):
        return self.get_score_team(2)

    @property
    def winning_team(self):
        """
        :return: id de la team qui vient de marquer le but, 0 sinon
        """
        return self._winning_team

    def copy(self):
        return deepcopy(self)

    def to_str(self):
        return "%d|%d|%d|%d|%s|%s" % (self._step, self.get_score_team(1), self.get_score_team(2),
                                      self._winning_team, self.ball,
                                      "|".join("%d:%d:%s" % (k[0], k[1], v.to_str()) for k, v in self._configs.items()))

    @classmethod
    def from_str(cls, strg):
        l_pos = strg.split("|")
        res = cls(step=int(l_pos[0]), score={1: int(l_pos[1]), 2: int(l_pos[2])}, winning_team=int(l_pos[3]))
        res._ball = MobileMixin.from_str(l_pos[4])
        for p in l_pos[5:]:
            cfg = p.split(":")
            res._configs[(int(cfg[0]), int(cfg[1]))] = Configuration.from_str(cfg[2])
        return res

    def apply_actions(self, actions=None):
        if not actions:
            return
        sum_of_shoots = Vector2D()
        for k, c in self._configs.items():
            if k in actions:
                sum_of_shoots += c.next(self.ball, actions[k])
        self.ball.vitesse.norm = self.ball.vitesse.norm - settings.ballBrakeSquare * self.ball.vitesse.norm ** 2 - settings.ballBrakeConstant * self.ball.vitesse.norm
        ## decomposition selon le vecteur unitaire de ball.speed
        snorm = sum_of_shoots.norm
        if snorm > 0:
            u_s = sum_of_shoots.copy()
            u_s.normalize()
            u_t = Vector2D(-u_s.y, u_s.x)
            speed_abs = abs(self.ball.vitesse.dot(u_s))
            speed_ortho = self.ball.vitesse.dot(u_t)
            speed = Vector2D(speed_abs * u_s.x - speed_ortho * u_s.y, speed_abs * u_s.y + speed_ortho * u_s.x)
            speed += sum_of_shoots
            self.ball.vitesse = speed
        self.ball.vitesse = self.ball.vitesse.norm_max(settings.maxBallAcceleration)
        self.ball.position += self.ball.vitesse
        self._step += 1
        if self._is_ball_inside_goal():
            self._do_win(2 if self.ball.position.x <= 0 else 1)
            return
        if self.ball.position.x < 0:
            self.ball.position.x = -self.ball.position.x
            self.ball.vitesse.x = -self.ball.vitesse.x
        if self.ball.position.y < 0:
            self.ball.position.y = -self.ball.position.y
            self.ball.vitesse.y = -self.ball.vitesse.y
        if self.ball.position.x > settings.GAME_WIDTH:
            self.ball.position.x = 2 * settings.GAME_WIDTH - self.ball.position.x
            self.ball.vitesse.x = -self.ball.vitesse.x
        if self.ball.position.y > settings.GAME_HEIGHT:
            self.ball.position.y = 2 * settings.GAME_HEIGHT - self.ball.position.y
            self.ball.vitesse.y = -self.ball.vitesse.y

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return self.to_str()

    def _do_win(self, i):
        self._inc_score_team(i)
        self._winning_team = i

    def _inc_score_team(self, idx):
        self._score[idx] += 1

    def _is_ball_inside_goal(self):
        return (self.ball.position.x <= 0 or self.ball.position.x >= settings.GAME_WIDTH) and abs(
                self.ball.position.y - (settings.GAME_HEIGHT / 2.)) < settings.GAME_GOAL_HEIGHT / 2.

    @classmethod
    def create_initial_state(cls, nb_players_1=0, nb_players_2=0):
        """ Creer un etat initial avec le nombre de joueurs indique
        :param nb_players_1: nombre de joueur de la team 1
        :param nb_players_2: nombre de joueur de la teamp 2
        :return:
        """
        state = cls()
        state.reset_state(nb_players_1, nb_players_2)
        return state

    def reset_state(self, nb_players_1=0, nb_players_2=0):
        if nb_players_1 == 0 and self.nb_players(1) > 0:
            nb_players_1 = self.nb_players(1)
        if nb_players_2 == 0 and self.nb_players(2) > 0:
            nb_players_2 = self.nb_players(2)
        quarters = [i * settings.GAME_HEIGHT / 4 for i in range(1, 4)]
        rows = [settings.GAME_WIDTH * 0.1, settings.GAME_WIDTH * 0.35, settings.GAME_WIDTH * (1 - 0.35),
                settings.GAME_WIDTH * (1 - 0.1)]
        if nb_players_1 == 1:
            self._configs[(1, 0)] = Configuration.from_position(rows[0], quarters[1])
        if nb_players_2 == 1:
            self._configs[(2, 0)] = Configuration.from_position(rows[3], quarters[1])
        if nb_players_1 == 2:
            self._configs[(1, 0)] = Configuration.from_position(rows[0], quarters[0])
            self._configs[(1, 1)] = Configuration.from_position(rows[0], quarters[2])
        if nb_players_2 == 2:
            self._configs[(2, 0)] = Configuration.from_position(rows[3], quarters[0])
            self._configs[(2, 1)] = Configuration.from_position(rows[3], quarters[2])
        if nb_players_1 == 4:
            self._configs[(1, 0)] = Configuration.from_position(rows[0], quarters[0])
            self._configs[(1, 1)] =  Configuration.from_position(rows[0], quarters[2])
            self._configs[(1, 2)] = Configuration.from_position(rows[1], quarters[0])
            self._configs[(1, 3)] = Configuration.from_position(rows[1], quarters[2])
        if nb_players_2 == 4:
            self._configs[(2, 0)] = Configuration.from_position(rows[2], quarters[0])
            self._configs[(2, 1)] = Configuration.from_position(rows[2], quarters[2])
            self._configs[(2, 2)] = Configuration.from_position(rows[3], quarters[0])
            self._configs[(2, 3)] = Configuration.from_position(rows[3], quarters[2])
        self._ball = MobileMixin.from_position(settings.GAME_WIDTH / 2, settings.GAME_HEIGHT / 2)
        self._winning_team=0

###############################################################################
# SoccerTeam
###############################################################################

Player = namedtuple("Player", ["name", "strategy"])

class SoccerTeam(object):
    """ Equipe de foot. Comporte une  liste ordonnee de nom de joueurs et leur strategie.
    """
    def __init__(self, name=None, players=None, login=None):
        """
        :param name: nom de l'equipe
        :param players: liste de joueur Player(name,strategy)
        :return:
        """
        self._name, self._players, self._login = name, players, login

    @property
    def name(self):
        """
        :return: nom de l'equipe
        """
        return self._name

    @property
    def players_name(self):
        """
        :return: liste des noms des joueurs de l'equipe
        """
        return [x.name for x in self._players]

    @property
    def login(self):
        """
        :return: le login
        """
        return self._login if self._login else ""

    def player_name(self, idx):
        """
        :param idx: numero du joueur
        :return: nom du joueur
        """
        return self._players[idx].name

    @property
    def strategies(self):
        """
        :return: liste des strategies des joueurs
        """
        return [x.strategy for x in self._players]

    def strategy(self, idx):
        """
        :param idx: numero du joueur
        :return: strategie du joueur
        """
        return self._players[idx].strategy

    def compute_strategies(self, state, id_team):
        """ calcule les actions de tous les joueurs
        :param state: etat courant
        :param id_team: numero de l'equipe
        :return: dictionnaire action des joueurs
        """
        return dict([((id_team, i), x.strategy.compute_strategy(state.copy(), id_team, i)) for i, x in
                     enumerate(self._players)])

    @property
    def nb_players(self):
        """
        :return: nombre de joueurs
        """
        return len(self._players)

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return self.to_str()

    def to_str(self):
        return "%s|%s" % (self.name, "|".join("%s|%s" % (p, s) for (p, s) in zip(self.players_name, self.strategies)))

    @classmethod
    def from_str(cls, strg):
        l_str = strg.split("|")
        return cls(l_str[0], [Player(name=n,strategy=s) for n,s in zip(l_str[1::2], l_str[2::2])])  ##### BUG NE CHARGE PAS LES STRATS OBV

    def copy(self):
        return deepcopy(self)


class SoccerMatch(object):
    """ Match de foot.
    """
    def __init__(self, team1=None, team2=None,max_steps=settings.MAX_GAME_STEPS):
        """
        :param team1: premiere equipe
        :param team2: deuxieme equipe
        :return:
        """
        self._team1, self._team2, self.max_steps = team1, team2, max_steps
        self._listeners = SoccerEvents()
        self._state = None # SoccerState.create_initial_state(self._team1.nb_players,self._team2.nb_players)
        self._states = [] #[self.state]
        self._thread = None
        self._on_going = False
        self._lock = Lock()
        self._kill = False
        self._replay = False
        self._step_replay = 0
    @property
    def state(self):
        """
        :return: etat courant
        """
        return self._state.copy()

    @property
    def team1(self):
        return self._team1

    @property
    def team2(self):
        return self._team2

    def play(self, join=True):
        """ joue le match
        :param join: attend que le match soit fini avant de sortir
        :return:
        """
        if not self._thread or not self._thread.isAlive():
            self._thread = threading.Thread(target=self._play)
            self._thread.start()
            if join:
                self._thread.join()
                return self.state.score_team1,self.state.score_team2
        return (None,None)

    def reset(self):
        self.kill()
        self._state = None
        self._step_replay = 0
        if not self._replay:
            self._states = []
        self._thread = None
        self._on_going = False

    def get_score(self,idx):
        return self.state.get_score_team(idx)

    def get_team(self, i):
        if i == 1:
            return self.team1
        if i == 2:
            return self.team2
        return None

    def kill(self):
        """ arrete le match
        :return:
        """
        self._kill = True
        time.sleep(0.1)
        self._kill = False

    def _next_step(self):
        self._lock.acquire()
        if not self._on_going:
            self._lock.release()
            return
        if self._replay:
            self._step_replay += 1
            if self._step_replay >= len(self._states):
                self._lock.release()
                return
        if self._state.winning_team > 0:
            self._listeners.end_round(self.team1, self.team2, self.state)
            if self._replay:
                self._state = self._states[self._step_replay]
            else:
                self._state.reset_state()
            self._listeners.begin_round(self.team1, self.team2, self.state)
            self._lock.release()
            return
        if self._replay:
            self._state = self._states[self._step_replay]
        else:
            actions = self.team1.compute_strategies(self.state, 1)
            actions.update(self.team2.compute_strategies(self.state, 2))
            self._state.apply_actions(actions)
        self._lock.release()

    def _begin_match(self):
        if self._on_going:
            return
        self._on_going = True
        if self._replay:
            self._step_replay = 0
            self._state = self._states[self._step_replay]
            self._listeners.begin_match(self.team1, self.team2, self.state)
            self._listeners.begin_round(self.team1, self.team2, self.state)
            return
        self._state = SoccerState.create_initial_state(self._team1.nb_players, self._team2.nb_players)
        self._states = [self.state]
        self._listeners.begin_match(self.team1, self.team2, self.state)
        self._listeners.begin_round(self.team1, self.team2, self.state)
        for s in self.team1.strategies + self.team2.strategies:
            self._listeners += s

    def _play(self):
        if not self._thread or self._on_going:
            return
        self._begin_match()
        while not self._kill and ((not self._replay and self._state.step < self.max_steps) or \
                            (self._replay and self._step_replay<len(self._states)-1)):
            self._next_step()
            if not self._replay:
                self._states.append(self.state)
            self._listeners.update_round(self.team1, self.team2, self.state)
        self._on_going = False
        self._replay = True
        self._listeners.end_match(self.team1, self.team2, self.state)

    def send_to_strategies(self, cmd):
        self._lock.acquire()
        for s in self.team1.strategies + self.team2.strategies:
            if hasattr(s, "listen"):
                s.listen(cmd)
        self._lock.release()

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return self.to_str()

    def copy(self):
        return deepcopy(self)

    def to_str(self):
        return "%s\n%s\n%s" % (str(self.team1), str(self.team2), "\n".join(str(s) for s in self._states))

    @classmethod
    def from_str(cls, strg):
        l_tmp = strg.split("\n")
        res = cls(SoccerTeam.from_str(l_tmp[0]), SoccerTeam.from_str(l_tmp[1]))
        res._states = [SoccerState.from_str(x) for x in l_tmp[2:] if len(x) > 0]
        res._state = res._states[-1]
        res._replay = True
        return res



###############################################################################
# Tournament
###############################################################################


@total_ordering
class Score(object):
    def __init__(self):
        self.win = 0
        self.loose = 0
        self.draw = 0
        self.gf = 0
        self.ga = 0

    @property
    def diff(self):
        return self.gf - self.ga

    @property
    def points(self):
        return 3 * self.win + self.draw

    @property
    def score(self):
        return self.points,self.win,self.draw,self.loose,self.gf,self.ga

    def set(self,score=None):
        if score is None:
            self.win, self.loose, self.draw, self.gf, self.ga = 0, 0, 0, 0, 0
            return
        self.win, self.loose, self.draw, self.gf, self.ga = score.win, score.loose, score.draw, score.gf, score.ga

    def add(self,gf,ga):
        self.gf += gf
        self.ga += ga
        if gf > ga:
            self.win+=1
        if gf == ga:
            self.draw += 1
        if gf < ga:
            self.loose += 1

    def __str__(self):
        return "\033[92m\033[34m%d\033[0m (\033[32m%d\033[0m,\033[31m%d\033[0m,\033[93m%d\033[0m) - (%d,%d)" % \
               (self.points,self.win,self.draw,self.loose,self.gf,self.ga)

    def str_nocolor(self):
        return "%d (%d,%d,%d) - [%d,%d] " % (self.points,self.win,self.draw,self.loose,self.gf,self.ga)

    def __lt__(self,other):
        return (self.points,self.diff,self.gf,-self.ga) < (other.score,other.diff,other.gf,-other.ga)

    def __eq__(self,other):
        return (self.points,self.diff,self.gf,-self.ga) == (other.score,other.diff,other.gf,-other.ga)

    def to_str(self):
        return "(%d,%d,%d,%d,%d)" % (self.win,self.draw,self.loose,self.gf,self.ga)

    @classmethod
    def from_str(cls,strg):
        res=cls()
        res.win, res.draw, res.loose, res.gf, res.ga = [int(x) for x in strg.lstrip("(").rstrip(")").split(",")]
        return res

class SoccerTournament(object):

    TeamTuple = namedtuple("TeamTuple",["team","score"])
    SEP_MATCH="#####MATCH#####\n"

    def __init__(self,nb_players=None, max_steps=settings.MAX_GAME_STEPS,retour=True):
        self.nb_players, self.max_steps, self._retour = nb_players,  max_steps, retour
        self._matches = dict()
        self._teams = []
        self._listeners = SoccerEvents()
        self.cur_match, self._list_matches = None, None
        self._over, self._on_going = False, False
        self.cur_i, self.cur_j= -1, -1
        self.verbose = True
        self._kill = False
        self._replay = False

    def add_team(self,team, score = None):
        if score is None:
            score = Score()
        if self.nb_players and self.nb_players!=team.nb_players:
            return False
        self._teams.append(self.TeamTuple(team,score))
        if self.nb_teams > 1 :
            for i,t in enumerate(self.teams[:-1]):
                self._matches[(i,self.nb_teams-1)]=SoccerMatch(t,team,self.max_steps)
                if self._retour: self._matches[(self.nb_teams-1,i)]=SoccerMatch(team,t,self.max_steps)
        return True

    def get_team(self,i):
        if type(i) == str:
            i = self.find_team(i)
        return self._teams[i].team

    def reset(self):
        self.cur_match = None
        self._list_matches = None
        self._on_going = False
        for t in self._teams:
            t.score.set()
        for m in self._matches.values():
            m.reset()

    @property
    def nb_teams(self):
        return len(self.teams)

    @property
    def teams(self):
        return [t.team for t in self._teams]

    @property
    def nb_matches(self):
        return len(self._matches)

    def play(self):
        if self._on_going:
            return
        self._on_going = True
        self._list_matches = sorted(self._matches.items())
        self.play_next()


    def kill(self):
        self._kill = True
        if hasattr(self.cur_match, "kill"):
            self.cur_match.kill()

    def play_next(self):
        if len(self._list_matches)==0 or self._kill:
            self._on_going = False
            self._kill = False
            if self.verbose:
                print("Fin tournoi")
            return
        (self.cur_i, self.cur_j), self.cur_match=self._list_matches.pop(0)
        self.cur_match._listeners += self
        self.cur_match.play(False)

    def find_team(self,name):
        for i,t in enumerate(self._teams):
            if t.team.name==name:
                return i
        return -1

    def get_score(self,i):
        return self._teams[i].score

    def get_match(self,i,j):
        if type(i)==str and type(j)==str:
            i = self.find_team(i)
            j = self.find_team(j)
        return self._matches[(i,j)]

    def get_matches(self,i):
        if type(i) == str:
            i = self.find_team(i)
        return [m for k,m in self._matches.items() if k[0] == i or k[1] == i]

    def format_scores(self):
        sc = sorted([(t.score,t.team) for t in self._teams ],reverse=True)
        res=["\033[92m%s\033[0m (\033[93m%s\033[m) : %s" % (team.name,team.login,str(score))for score,team in sc]
        return "\033[93m***\033[0m \033[95m Resultats pour le tournoi \033[92m%d joueurs\033[0m : \033[93m***\33[0m \n\t%s\n\n" %\
                            (self.nb_teams,"\n\t".join(res))

    def to_str(self):
        res="%d|%d|%d\n" % (self.nb_players if self.nb_players is not None else 0, len(self._teams), int(self._retour))
        res+="\n".join("%d,%s\n%s" % (i,team.score.to_str(),team.team.to_str()) for i,team in enumerate(self._teams))
        res+="\n%s" %(self.SEP_MATCH,)
        res+=self.SEP_MATCH.join( "%d,%d\n%s\n" % (k[0],k[1],match) for k,match in sorted(self._matches.items()))
        return res

    @classmethod
    def from_str(cls,strg):
        res=cls()
        l_strg=strg.split(cls.SEP_MATCH)
        cur_l = l_strg[0].split("\n")
        res.nb_players, nb_teams, res._retour = [int(x) for x in cur_l.pop(0).split("|")]
        while len(cur_l)>0:
            info = cur_l.pop(0)
            if len(info) == 0:
                continue
            fvir = info.index(",")
            idx,sc_str=info[:fvir],info[fvir+1:]
            assert(len(res._teams)==int(idx))
            score=Score.from_str(sc_str)
            team = SoccerTeam.from_str(cur_l.pop(0))
            res.add_team(team,score)
        for l in l_strg[1:]:
            if len(l)==0:
                continue
            t1 = int(l[:l.index(",")])
            t2 = int(l[l.index(",")+1:l.index("\n")])
            match = SoccerMatch.from_str(l[l.index("\n")+1:])
            res._matches[(t1, t2)] = match
        res._replay = True
        return res

    def update_round(self,*args,**kwargs):
        self._listeners.update_round(*args,**kwargs)

    def begin_match(self,*args,**kwargs):
        if self.verbose:
         print("Debut match %d/%d : %s vs %s" %(self.nb_matches - len(self._list_matches),self.nb_matches,
                                                   self.cur_match.get_team(1).name,self.cur_match.get_team(2).name))
        self._listeners.begin_match(*args,**kwargs)

    def begin_round(self, *args, **kwargs):
        self._listeners.begin_round(*args,**kwargs)

    def end_round(self, *args, **kwargs):
        self._listeners.end_round(*args,**kwargs)

    def end_match(self, *args, **kwargs):
        if not self._replay:
            self._teams[self.cur_i].score.add(self.cur_match.get_score(1), self.cur_match.get_score(2))
            self._teams[self.cur_j].score.add(self.cur_match.get_score(2), self.cur_match.get_score(1))
        if self.verbose:
            print("Fin match  %s vs %s : %d - %d" % (self.cur_match.get_team(1).name,self.cur_match.get_team(2).name,\
                                                     self.cur_match.get_score(1),self.cur_match.get_score(2)))
        self._listeners.end_match(*args,**kwargs)
        self.cur_match._listeners -= self
        self.play_next()


