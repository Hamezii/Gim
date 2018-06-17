'''
GIM Descent 4

James Lecomte

To do:
- Make enemies do different things when attacking ie. goblins explode when attacking

- Maybe implement an event system, where Systems emit events which other Systems recieve

- Fix the grid cache system
 - I think this is done


'''

# VV Do this to profile VV
# py -m cProfile -s tottime gim.pyw

import glob
import random
import sys

import pygame

import ecs
import ui
import renderer
import constants


FULLSCREEN_MODE = True
MUSIC_VOLUME = 1


pygame.mixer.pre_init(44100, -16, 8, 2048)
pygame.init()
pygame.mixer.init()

#random.seed(1)



def leave():
    """Close the game."""
    sys.exit(0)


# CLASSES

class DynamicPos:
    """A vector value which linearly interpolates to a position."""

    def __init__(self, pos, speed):
        self.current = pos
        self.goal = pos
        self.speed = speed

    def move(self, pos, instant=False):
        """Set a target position. Instant moves it there instantly."""
        self.goal = pos
        if instant:
            self.current = pos

    def update(self, delta):
        """Linearly interpolate to target position."""
        x = (self.goal[0] - self.current[0])*min(1, delta*self.speed*0.001)
        y = (self.goal[1] - self.current[1])*min(1, delta*self.speed*0.001)
        self.current = (self.current[0]+x, self.current[1] + y)

    @property
    def x(self):
        """Get x value of vector."""
        return self.current[0]

    @property
    def y(self):
        """Get y value of vector."""
        return self.current[1]


class Camera:
    """The game camera.

    Can follow a point and shake.
    """

    def __init__(self, speed):
        self._ppt = round(constants.MENU_SCALE*1.5)*20
        self._shake = 0
        self._shake_x = 0
        self._shake_y = 0
        self._pos = DynamicPos((0, 0), speed=speed)

        self._t_lastshake = 0
        self.start = True

    def get_rect(self):
        """Return the rect in which the camera can see.

        Rect position and size is in pixels.
        """
        x = (self._pos.x + random.uniform(-self._shake_x, self._shake_x)) * self._ppt / constants.TILE_SIZE
        y = (self._pos.y + random.uniform(-self._shake_y, self._shake_y)) * self._ppt / constants.TILE_SIZE
        rect = pygame.Rect(0, 0, constants.WIDTH, constants.HEIGHT)
        rect.center = (x, y)
        return rect

    def get_scale(self):
        """Return scale of camera. Larger number means more zoomed in."""
        return self._ppt / constants.TILE_SIZE

    def get_zoom(self):
        """Get pixels per tile of camera. Larger number means larger tiles."""
        return self._ppt

    def zoom(self, zoom):
        """Change the pixels per tile of the camera. Positive zoom means zooming in."""
        self._ppt += zoom

    def shake(self, amount):
        """Shake the camera."""
        self._shake += amount

    def set(self, pos, direct=False):
        """Set target position of the camera."""
        self._pos.move(pos, direct)

    def tile_to_pixel_pos(self, x, y):
        """Including zoom, return the position of the center of a tile relative to the top-left of the map."""
        return ((x+0.5)*self._ppt, (y+0.5)*self._ppt)

    def tile_to_camera_pos(self, x, y):
        """Excluding zoom, return the position of the center of a tile relative to the top-left of the map."""
        return ((x+0.5)*constants.TILE_SIZE, (y+0.5)*constants.TILE_SIZE)

    def tile_to_screen_pos(self, x, y):
        """Return the position of the center of a tile relative to the top-left of the screen."""
        pixelpos = self.tile_to_pixel_pos(x, y)
        rect = self.get_rect()
        return (pixelpos[0] - rect.x, pixelpos[1] - rect.y)

    def update(self, t_frame, pos):
        """Update shake amount and move towards target position."""
        if self.start:
            self.start = False
            self.set(pos, direct=True)
        else:
            self.set(pos)

        self._pos.update(t_frame)

        self._t_lastshake += t_frame
        while self._t_lastshake >= 1000/30:
            self._t_lastshake -= 1000/30
            self._shake_x = random.uniform(-self._shake, self._shake)
            self._shake_y = random.uniform(-self._shake, self._shake)

            self._shake *= 0.75
            if self._shake < 0.1:
                self._shake = 0


class Game:
    """The game. Can perform functions on the ECS."""

    def __init__(self):
        self.camera = Camera(speed=10)
        self.world = ecs.World(self)

    def entity_image(self, entity, scale):
        """Return the current image of an entity referred to by its id."""
        args = {}

        # Name
        name = self.world.entity_component(entity, ecs.RenderC).imagename

        # Color
        color = [0, 0, 0]
        if self.world.has_component(entity, ecs.FireElementC) or self.world.has_component(entity, ecs.BurningC):
            color[0] += 100
        if self.world.has_component(entity, ecs.IceElementC):
            color[0] += 0
            color[1] += 50
            color[2] += 100
        if any(color):
            args["color"] = (color[0], color[1], color[2], pygame.BLEND_ADD)

        # Blinking
        if entity != self.world.tags.player:
            if self.world.has_component(entity, ecs.InitiativeC):
                entity_nextturn = self.world.entity_component(entity, ecs.InitiativeC).nextturn
                player_nextturn = self.world.entity_component(self.world.tags.player, ecs.InitiativeC).nextturn
                if entity_nextturn <= player_nextturn:
                    args["blinking"] = True

        '''

        if self.world.has_component(entity, ecs.FrozenC):
            args["frozen"] = True


        # Icons
        icons = []

        if self.world.has_component(entity, ecs.FireElementC):
            icons.append(("elementFire", None))

        if self.world.has_component(entity, ecs.IceElementC):
            icons.append(("elementIce", None))

        if self.world.has_component(entity, ecs.ExplosiveC):
            explosive = self.world.entity_component(entity, ecs.ExplosiveC)
            if explosive.primed:
                icons.append(("explosive", explosive.fuse))

        if self.world.has_component(entity, ecs.FreeTurnC):
            freeturn = self.world.entity_component(entity, ecs.FreeTurnC)
            icons.append(("free-turn", freeturn.life))

        if icons:
            args["icons"] = icons
        '''

        # Getting image
        img = RENDERER.get_image(name=name, scale=scale, **args)
        return img

    def draw_centered_entity(self, surface, entity, scale, pos):
        """Draw an entity, including icons etc."""
        entity_surface = self.entity_image(entity, scale)

        RENDERER.draw_centered_image(surface, entity_surface, pos)

        if self.world.has_component(entity, ecs.FrozenC):
            RENDERER.draw_centered_image(surface, RENDERER.get_image(name="ice-cube", scale=scale), pos)

        # Icons
        icons = []

        if self.world.has_component(entity, ecs.FireElementC):
            icons.append(("elementFire", None))

        if self.world.has_component(entity, ecs.IceElementC):
            icons.append(("elementIce", None))

        if self.world.has_component(entity, ecs.ExplosiveC):
            explosive = self.world.entity_component(entity, ecs.ExplosiveC)
            if explosive.primed:
                icons.append(("explosive", explosive.fuse))

        if self.world.has_component(entity, ecs.FreeTurnC):
            freeturn = self.world.entity_component(entity, ecs.FreeTurnC)
            icons.append(("free-turn", freeturn.life))

        ppt = scale * constants.TILE_SIZE
        for i, icon in enumerate(icons):
            image_name = icon[0]
            value = icon[1]

            icon_pos = (pos[0] + ppt*(-0.25 + i*0.2), pos[1] + ppt*0.2)
            RENDERER.draw_centered_image(surface, RENDERER.get_image(name=image_name, scale=scale), icon_pos)
            if value is not None:
                text_pos = (icon_pos[0], icon_pos[1]-ppt*0.3)
                RENDERER.draw_text(surface, constants.WHITE, text_pos, str(value), 10 * scale, centered=True)


    def teleport_entity(self, entity, amount):
        """Teleport an entity to a random position in a specific radius."""
        pos = self.world.entity_component(entity, ecs.TilePositionC)
        while True:
            randpos = (pos.x+random.randint(-amount, amount),
                       pos.y+random.randint(-amount, amount))
            if self.world.get_system(ecs.GridSystem).on_grid(randpos):
                if self.world.get_system(ecs.GridSystem).get_blocker_at(randpos) == 0:
                    self.world.get_system(ecs.GridSystem).move_entity(entity, randpos)
                    return

    def speed_entity(self, entity, amount):
        """Give an entity free turns."""
        if self.world.has_component(entity, ecs.FreeTurnC):
            self.world.entity_component(entity, ecs.FreeTurnC).life += amount
        else:
            self.world.add_component(entity, ecs.FreeTurnC(amount))

    def heal_entity(self, entity, amount):
        """Heal an entity for a certain amount of health."""
        if self.world.has_component(entity, ecs.HealthC):
            health = self.world.entity_component(entity, ecs.HealthC)
            health.current = min(health.max, health.current+amount)

    def generate_level(self):
        """Initialise the entities in the ECS."""
        grid = []
        gridwidth = self.world.get_system(ecs.GridSystem).gridwidth
        gridheight = self.world.get_system(ecs.GridSystem).gridheight

        for y in range(0, gridheight):  # Walls
            grid.append([])

            for x in range(0, gridwidth):
                grid[y].append(1)

        for roomy in range(0, gridheight):  # Rooms
            for roomx in range(0, gridwidth):
                roomheight = random.randint(2, 6)
                roomwidth = random.randint(2, 6)
                if roomx + roomwidth <= gridwidth and roomy + roomheight <= gridheight and random.randint(1, 15) == 1:
                    for y in range(0, roomheight):
                        for x in range(0, roomwidth):
                            grid[roomy+y][roomx+x] = 0

        for y in range(0, gridheight):
            for x in range(0, gridwidth):
                if grid[y][x]:                  # Creating walls on positions which have been marked
                    self.world.create_entity(
                        ecs.RenderC(random.choice(("wall1", "wall2"))),
                        ecs.TilePositionC(x, y),
                        ecs.BlockerC(),
                        ecs.DestructibleC(),
                    )
                else:
                    if random.randint(1, 45) == 1:      # Creating items
                        item = random.randint(1, 4)
                        if item == 1:
                            self.world.create_entity(
                                ecs.RenderC("potion-red"),
                                ecs.TilePositionC(x, y),
                                ecs.ItemC(consumable=True),
                                ecs.UseEffectC((self.heal_entity, 20))
                            )
                        if item == 2:
                            self.world.create_entity(
                                ecs.RenderC("potion-green"),
                                ecs.TilePositionC(x, y),
                                ecs.ItemC(consumable=True),
                                ecs.UseEffectC((self.speed_entity, 8))
                            )
                        if item == 3:
                            self.world.create_entity(
                                ecs.RenderC("potion-blue"),
                                ecs.TilePositionC(x, y),
                                ecs.ItemC(consumable=True),
                                ecs.UseEffectC((self.teleport_entity, 15))
                            )
                        if item == 4:
                            self.world.create_entity(
                                ecs.RenderC("bomb"),
                                ecs.TilePositionC(x, y),
                                ecs.ItemC(consumable=False),
                                ecs.ExplosiveC(3)
                            )
                    if random.randint(1, 30) == 1:       # Creating enemies
                        choice = random.randint(1, 3)
                        if choice == 1:
                            entity = self.world.create_entity(
                                ecs.AnimationC(idle=["ogre-i", "ogre-i", "ogre-i", "ogre-i2", "ogre-i3", "ogre-i3",
                                                 "ogre-i3", "ogre-i4"], ready=["ogre-r", "ogre-r", "ogre-i", "ogre-i"]),
                                ecs.RenderC(),
                                ecs.TilePositionC(x, y),
                                ecs.AIC(),
                                ecs.MovementC(diagonal=False),
                                ecs.InitiativeC(3),
                                ecs.BlockerC(),
                                ecs.HealthC(10),
                                ecs.AttackC(10),
                                ecs.ExplosiveC(3)
                            )
                        if choice == 2:
                            entity = self.world.create_entity(
                                ecs.AnimationC(idle=["snake-i", "snake-i", "snake-i2", "snake-i2"], ready=[
                                    "snake-r", "snake-r", "snake-r2", "snake-r2"]),
                                ecs.RenderC(),
                                ecs.TilePositionC(x, y),
                                ecs.AIC(),
                                ecs.MovementC(diagonal=True),
                                ecs.InitiativeC(2),
                                ecs.BlockerC(),
                                ecs.HealthC(5),
                                ecs.AttackC(5),
                            )

                        if choice == 3:
                            entity = self.world.create_entity(
                                ecs.AnimationC(idle=["golem-stone-i", "golem-stone-i", "golem-stone-i", "golem-stone-r", "golem-stone-r",
                                                 "golem-stone-r"], ready=["golem-stone-i", "golem-stone-i", "golem-stone-r", "golem-stone-r"]),
                                ecs.RenderC(),
                                ecs.TilePositionC(x, y),
                                ecs.AIC(),
                                ecs.MovementC(diagonal=False),
                                ecs.InitiativeC(3),
                                ecs.BlockerC(),
                                ecs.HealthC(30),
                                ecs.AttackC(10),
                            )

                        if random.randint(1, 5) == 1:
                            self.world.add_component(entity, ecs.FireElementC())
                        if random.randint(1, 5) == 1:
                            self.world.add_component(entity, ecs.IceElementC())


# MAIN

def get_input():
    """Return the key that was just pressed."""
    keypress = None

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            leave()

        if event.type == pygame.KEYDOWN:
            keypress = event.key

            if event.key == pygame.K_ESCAPE:
                leave()

            if event.key == pygame.K_w or event.key == pygame.K_UP:
                keypress = constants.UP

            if event.key == pygame.K_a or event.key == pygame.K_LEFT:
                keypress = constants.LEFT

            if event.key == pygame.K_s or event.key == pygame.K_DOWN:
                keypress = constants.DOWN

            if event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                keypress = constants.RIGHT

    return keypress


def main():
    """Run the game."""
    game = Game()

    game.world.add_system(ecs.GridSystem())
    game.world.add_system(ecs.InitiativeSystem())

    game.world.add_system(ecs.PlayerInputSystem())
    game.world.add_system(ecs.AISystem())
    game.world.add_system(ecs.FreezingSystem())
    game.world.add_system(ecs.BurningSystem())
    game.world.add_system(ecs.BumpSystem())

    game.world.add_system(ecs.ExplosionSystem())
    game.world.add_system(ecs.DamageSystem())
    game.world.add_system(ecs.RegenSystem())
    game.world.add_system(ecs.PickupSystem())
    game.world.add_system(ecs.IdleSystem())

    game.world.add_system(ecs.AnimationSystem())

    game.generate_level()

    game.world.tags.focus = game.world.tags.player = game.world.create_entity(
        ecs.RenderC("magnum"),
        ecs.TilePositionC(0, 0),
        ecs.PlayerInputC(),
        ecs.MovementC(),
        ecs.InitiativeC(1),
        ecs.BlockerC(),
        ecs.HealthC(50),
        ecs.InventoryC(10),
        ecs.AttackC(5)
    )
    game.world.get_system(ecs.GridSystem).update()
    game.teleport_entity(game.world.tags.player, game.world.get_system(ecs.GridSystem).gridwidth)

    RENDERER.camera = game.camera
    UI.add_menu(ui.MainMenu(game))

    debugging = False

    while True:

        delta = CLOCK.tick()
        fps = CLOCK.get_fps()
        if fps != 0:
            avgms = 1000/fps
        else:
            avgms = delta

        SCREEN.fill(constants.BLACK)

        keypress = get_input()

        if keypress == pygame.K_MINUS:  # Zooming out
            if game.camera.get_zoom() > 20:
                game.camera.zoom(-20)

        if keypress == pygame.K_EQUALS:  # Zooming in
            game.camera.zoom(20)

        if keypress == pygame.K_F12:
            debugging = not debugging

        UI.send_event(("input", UI.get_focus(), keypress))

        done = False
        t_frame = delta
        while not done:
            game.world.update(playerinput=None, t_frame=t_frame)
            t_frame = 0
            if game.world.has_component(game.world.tags.player, ecs.MyTurnC):
                done = True

        RENDERER.t_elapsed += delta
        UI.send_event(("update", avgms))
        UI.draw_menus(SCREEN)

        if debugging:
            print_debug_info(game)

        pygame.display.update()

def print_debug_info(game):
    """Show debug info in the topleft corner."""
    fps = CLOCK.get_fps()
    infos = (
        "FPS: " + str(int(fps)),
        "TOTAL IMAGES: " + str(RENDERER.total_images),
        "NEXTTURN: " + str(game.world.entity_component(game.world.tags.player, ecs.InitiativeC).nextturn),
        "TICK: " + str(game.world.get_system(ecs.InitiativeSystem).tick)
    )
    for i, info in enumerate(infos):
        RENDERER.draw_text(SCREEN, (200, 50, 50), (0, 12*i), info, 10)


def init_screen():
    """Returns the screen surface, as well as WIDTH and HEIGHT constants."""
    if FULLSCREEN_MODE:
        info_object = pygame.display.Info()
        width = info_object.current_w
        height = info_object.current_h
        screen = pygame.display.set_mode(
            (width, height), pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
    else:
        width = 1200
        height = 800
        screen = pygame.display.set_mode((width, height))

    return (screen, width, height)

if __name__ == "__main__":
    CLOCK = pygame.time.Clock()

    # VARIABLES
    SCREEN, constants.WIDTH, constants.HEIGHT = init_screen()

    constants.MENU_SCALE = round(constants.WIDTH/600)

    # Initialising audio
    SOUNDS = {}
    for au in glob.glob(constants.AUDIO+"*.wav"):
        auname = au[len(constants.AUDIO):-4]
        SOUNDS[auname] = pygame.mixer.Sound(au)

    RENDERER = renderer.Renderer()
    UI = ui.MenuManager(RENDERER)

    # Playing music
    pygame.mixer.music.load(random.choice(glob.glob(constants.MUSIC+"*")))
    pygame.mixer.music.set_volume(MUSIC_VOLUME)
    pygame.mixer.music.play(-1)

    main()
