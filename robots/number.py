from typing import Optional, List, Set
from collections import deque
from snakepit.robot_snake import RobotSnake
from snakepit.datatypes import Position, Vector
import functools
import logging
import random
import string
import contextlib
import time

logging.basicConfig()



@contextlib.contextmanager
def timer(name):
	start = time.time()
	yield
	took = time.time() - start
	logging.info(f'{name} took {took:.6f}')



class CannotContinue(Exception):
	pass



class NumberRobotSnake(RobotSnake):

	def __init__(self, game_settings, world, color):
		super().__init__(game_settings, world, color)
		self.length = 0
		self.head = Position(0, 0)
		self.tail = Position(0, 0)
		self.body: List[Position] = []
		self.current_direction: Optional[Vector]
		self.plan: deque[Position] = deque()
		self.plan_directions: deque[Vector] = deque()
		self.BLOCKS = {self.CH_STONE} | self.BODY_CHARS | self.DEAD_BODY_CHARS


	@functools.lru_cache(maxsize = 1600)
	def is_block(self, point: Position):
		if point.x < 0 or point.x >= self.world.SIZE_X or point.y < 0 or point.y >= self.world.SIZE_Y:
			return True
		char, color = self.world[point.y][point.x]
		return char in self.BLOCKS


	def iter_directions(self, preferred_direction: Vector, backup_directions: Set[Vector]):
		yield preferred_direction
		while backup_directions:
			choice = random.choice(list(backup_directions))
			backup_directions.remove(choice)
			yield choice


	def get_to(self, point: Position) -> None:
		self.plan.clear()
		self.plan_directions.clear()

		# current
		cx = self.head.x
		cy = self.head.y

		while not (cx == point.x and cy == point.y):
			# logging.info(f'Plan step {len(self.plan)}')

			dx = cx - point.x
			dy = cy - point.y

			if dx == 0:
				preferred_direction = self.UP if dy > 0 else self.DOWN
				backup_directions = {self.RIGHT, self.LEFT}
			elif dy == 0:
				preferred_direction = self.LEFT if dx > 0 else self.RIGHT
				backup_directions = {self.UP, self.DOWN}

			elif abs(dx) > abs(dy):
				preferred_direction = self.LEFT if dx > 0 else self.RIGHT
				backup_directions = {self.UP if dy > 0 else self.DOWN}
			else:
				preferred_direction = self.UP if dy > 0 else self.DOWN
				backup_directions = {self.LEFT if dx > 0 else self.RIGHT}

			for direction in self.iter_directions(preferred_direction, backup_directions):
				next_point = Position(cx + direction.xdir, cy + direction.ydir)
				if not(self.is_block(next_point) or next_point in self.plan or self.free_room(next_point) < 1.0):
					self.plan.append(next_point)
					self.plan_directions.append(direction)
					cx = next_point.x
					cy = next_point.y
					break
			else:
				raise CannotContinue()


	def flood_fill(self, point: Position):
		points_to_check = [point]
		done = set()
		while points_to_check:
			cp = points_to_check.pop()
			if cp not in done:
				if self.is_block(cp):
					continue
				yield cp
				# add neighborhood
				for direction in self.DIRECTIONS:
					next_point = Position(cp.x + direction.xdir, cp.y + direction.ydir)
					if next_point not in done:
						points_to_check.append(next_point)
			done.add(cp)


	def free_room(self, point: Position) -> float:
		points = 0
		for _ in self.flood_fill(point):
			points += 1
			if points >= self.length:
				return 1.0
		return points / self.length


	def get_position(self):
		self.body.clear()
		self.length = 0
		for y in range(self.world.SIZE_Y):
			for x in range(self.world.SIZE_X):
				char, color = self.world[y][x]

				if color == self.color:  # our snake
					if char == self.CH_TAIL:
						self.tail = Position(x, y)
					elif char == self.CH_HEAD:
						self.head = Position(x, y)
					elif char == self.CH_BODY:
						pass

					self.body.append(Position(x, y))
					self.length += 1
		# logging.info(f'Current head {self.head}')
		# logging.info(f'Current tail {self.tail}')


	def distance(self, point_1: Position, point_2: Position) -> int:
		return abs(point_1.x - point_2.x) + abs(point_1.y - point_2.y)


	def compute_score(self, bonus: int, distance: int) -> float:
		return bonus / distance


	def find_best(self) -> Optional[Position]:
		points = []
		for y in range(self.world.SIZE_Y):
			for x in range(self.world.SIZE_X):
				char, color = self.world[y][x]
				if char in string.digits:
					point = Position(x, y)
					distance = self.distance(self.head, point)
					points.append((self.compute_score(int(char), distance), point))
		try:
			best = max(points)
			# logging.info(f'Best position is {best[1]} with score {best[0]}')
			return best[1]
		except ValueError:
			return None

	def backup(self):
		directions = list(self.DIRECTIONS)
		random.shuffle(directions)
		unblocked = []
		for direction in directions:
			next_point = Position(self.head.x + direction.xdir, self.head.y + direction.ydir)
			if not self.is_block(next_point):
				free_room = self.free_room(next_point)
				if free_room == 1.0:
					return direction
				else:
					unblocked.append((free_room, direction))

		if unblocked:
			_, direction = max(unblocked)
			return direction
		return None


	def next_direction(self, initial=False):
		self.is_block.cache_clear()
		self.get_position()
		best = self.find_best()
		if best is None:
			return self.backup()
		try:
			self.get_to(best)
		except CannotContinue:
			return self.backup()

		if self.plan_directions:
			next_direction = self.plan_directions.popleft()
			return next_direction
		return self.backup()
