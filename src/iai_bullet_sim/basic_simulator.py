import os
import pybullet as pb
import random
import tempfile
from collections import namedtuple
from iai_bullet_sim.utils import res_pkg_path, Vector3, Point3, Quaternion, Frame, import_class
from iai_bullet_sim.multibody import MultiBody, JointDriver
from iai_bullet_sim.rigid_body import RigidBody, GEOM_TYPES, BULLET_GEOM_TYPES
from iai_bullet_sim.constraint import Constraint
from jinja2 import Template

# Visual shape structure. Assigns names to bullet's info structure.
VisualShape = namedtuple('VisualShape', ['bulletId', 'linkIndex', 'geometryType', 'dimensions', 'filename', 'localPosition', 'localOrientation', 'rgba'])

# Collision shape structure. Assigns names to bullet's info structure.
CollisionShape = namedtuple('CollisionShape', ['bulletId', 'linkIndex', 'geometryType', 'dimensions', 'filename', 'localPosition', 'localOrientation'])


def hsva_to_rgba(h, s, v, a):
    """
    Converts a HSVA color to a RGBA color.

    :param h: Hue
    :type h: int, float
    :param s: Saturation
    :type s: int, float
    :param v: Value
    :type v: int, float
    :param a: Alpha
    :type a: int, float
    :return: RGBA equivalent as list [r,g,b,a]
    :rtype: list
    """
    h_i = int(round(h*6))
    f = h*6 - h_i
    p = v * (1 - s)
    q = v * (1 - f*s)
    t = v * (1 - (1 - f) * s)
    if h_i==0:
        return [v, t, p, a]
    elif h_i==1:
        return [q, v, p, a]
    elif h_i==2:
        return [p, v, t, a]
    elif h_i==3:
        return [p, q, v, a]
    elif h_i==4:
        return [t, p, v, a]
    elif h_i==5:
        return [v, p, q, a]
    print('h_i is {}'.format(h_i))
    return [1,1,1,a]

def vec3_to_list(vec):
    """
    Converts an indexable structure with len >= 3 to a list containing the first three elements.

    :type vec: iterable
    :rtype: list
    """
    return [vec[0], vec[1], vec[2]]

def vec_add(a, b):
    """
    Performs per element addition on two indexable structures with len >= 3 and returns the result as Vector3.

    :type a: iterable
    :type b: iterable
    :rtype: iai_bullet_sim.utils.Vector3
    """
    return Vector3(a[0] + b[0], a[1] + b[1], a[2] + b[2])

def vec_sub(a, b):
    """
    Performs per element subtraction on two indexable structures with len >= 3 and returns the result as Vector3.

    :type a: iterable
    :type b: iterable
    :rtype: iai_bullet_sim.utils.Vector3
    """
    return Vector3(a[0] - b[0], a[1] - b[1], a[2] - b[2])

def vec_scale(a, x):
    """
    Performs per element multiplication on an indexable structure with len >= 3 and returns the result as Vector3.

    :type a: iterable
    :type x: iterable
    :rtype: iai_bullet_sim.utils.Vector3
    """
    return Vector3(a.x * x, a.y * x, a.z * x)

def invert_transform(frame_tuple):
    """
    Inverts the transformation represented by the Frame datatype and returns it as new frame.

    :type frame_tuple:  iai_bullet_sim.utils.Frame
    :rtype: iai_bullet_sim.utils.Frame
    """
    temp = pb.invertTransform(list(frame_tuple.position), list(frame_tuple.quaternion))
    return Frame(Point3(*temp[0]), Quaternion(*temp[1]))

def transform_point(transform, point):
    """
    Transforms a given point by the given transform.

    :type transform: iai_bullet_sim.utils.Frame
    :type point: iterable
    :rtype: tuple
    """
    point, _ = pb.multiplyTransforms(transform.position, transform.quaternion, point, [0,0,0,1])
    return point

def transform_vector(transform, vector):
    """
    Transforms a given point by the given transform.

    :type transform: iai_bullet_sim.utils.Frame
    :type point: iterable
    :rtype: tuple
    """
    vec, _ = pb.multiplyTransforms((0,0,0), transform.quaternion, vector, [0,0,0,1])
    return vec

class ContactPoint(object):
    """Wrapper for bullet's contact point structure."""
    def __init__(self, bodyA, bodyB, linkA, linkB, posOnA, posOnB, normalOnB, dist, normalForce):
        """
        :param bodyA: Reference to first body
        :type  bodyA: MultiBody, RigidBody
        :param bodyB: Reference to second body
        :type  bodyB: MultiBody, RigidBody
        :param linkA: Link of first body; None in case of rigid body
        :type  linkA: str, NoneType
        :param linkB: Link of second body; None in case of rigid body
        :type  linkB: str, NoneType
        :param posOnA: Coordinates of contact on link of A
        :type  posOnA: iterable, iai_bullet_sim.utils.Vector3
        :param posOnB: Coordinates of contact on link of B
        :type  posOnB: iterable, iai_bullet_sim.utils.Vector3
        :param normalOnB: Normal direction of the contact
        :type  normalOnB: iterable, iai_bullet_sim.utils.Vector3
        :param dist: Penetration depth of the contact
        :type  dist: float
        :param normalForce: Force vector of the contact
        :type  normalForce: iterable, iai_bullet_sim.utils.Vector3
        """
        self.bodyA = bodyA
        self.bodyB = bodyB
        self.linkA = linkA
        self.linkB = linkB
        self.posOnA = posOnA
        self.posOnB = posOnB
        self.normalOnB = normalOnB
        self.dist = dist
        self.normalForce = normalForce

    def __leq__(self, other):
        """
        Compares the distances of two contact points.

        :type other: ContactPoint
        :rtype: float
        """
        return self.dist <= other.dist


class BasicSimulator(object):
    """Class wrapping the PyBullet interface in an object oriented manner."""
    def __init__(self, tick_rate=50, gravity=[0,0,-9.81]):
        """Constructs a simulator.

        :param tick_rate: Ticks ideally performed per second.
        :type  tick_rate: float
        :param   gravity: Gravity force for the simulation.
        :type    gravity: list
        """
        self.physicsClient = None
        self.bodies        = {}
        self.deletion_cbs  = {}
        self.constraints   = {}
        self.constraint_deletion_cbs = {}
        self.tick_rate   = tick_rate
        self.gravity     = gravity
        self.time_step   = 1.0 / self.tick_rate
        self.__client_id = 0
        self.__n_updates = 0
        self.__bId_IdMap = {}
        self.__cId_IdMap = {}

        self.__h = random.random()
        self.__nextId = 0
        self.__joint_types = {'fixed':  pb.JOINT_FIXED,    'prismatic': pb.JOINT_PRISMATIC, 
                              'hinge':  pb.JOINT_REVOLUTE, 'spherical': pb.JOINT_SPHERICAL,
                              'planar': pb.JOINT_PLANAR,   'p2p':       pb.JOINT_POINT2POINT}

        self.__plugins = set()
        f = open(res_pkg_path('package://iai_bullet_sim/urdf/single_mesh.urdf'), 'r')
        self.__mesh_template  = Template(f.read())
        f.close()
        self._temp_mesh_urdfs = {}

    def get_n_update(self):
        """Returns the number of performed updates.

        :rtype: int
        """
        return self.__n_updates

    def client_id(self):
        return self.__client_id

    def __gen_next_color(self):
        """Internal. Generates a new random color.

        :rtype: list
        """
        self.__h += 0.618033988749895
        self.__h %= 1.0
        return hsva_to_rgba(self.__h, 0.7, 0.95, 1.0)


    def init(self, mode='direct'):
        """Initializes the connection to Bullet.

        :param mode: Mode of the connection. Options: gui | direct
        :type  mode: str
        """
        while True:
            if pb.getConnectionInfo(self.__client_id)['isConnected'] > 0:
                self.__client_id += 1
            else:
                break

        self.physicsClient = pb.connect({'gui': pb.GUI, 'direct': pb.DIRECT}[mode], self.__client_id)#or p.DIRECT for non-graphical version
        pb.setGravity(*self.gravity, physicsClientId=self.__client_id)
        pb.setTimeStep(self.time_step, physicsClientId=self.__client_id)


    def set_tick_rate(self, tick_rate):
        """Updates the tick rate of the simulation.

        :type tick_rate: int
        """
        self.tick_rate = tick_rate
        self.time_step = 1.0 / self.tick_rate
        if self.physicsClient is not None:
            pb.setTimeStep(self.time_step, physicsClientId=self.__client_id)


    def set_gravity(self, gravity):
        """Updates the simulations gravity.

        :type gravity: list
        """
        self.gravity = gravity
        if self.physicsClient is not None:
            pb.setGravity(*gravity, physicsClientId=self.__client_id)

    def stop(self):
        """Stops the simulation. Calls disable() on all plugins."""
        for plugin in self.__plugins:
            plugin.disable(self)

    def kill(self):
        """Kills the connection to Bullet."""
        pb.disconnect(self.__client_id)
        for _, p in self._temp_mesh_urdfs.items():
            os.remove(p)

    def pre_update(self):
        """Called before every physics step."""
        for plugin in self.__plugins:
            plugin.pre_physics_update(self, self.time_step)

    def physics_update(self):
        """Steps the physics simulation."""
        pb.stepSimulation(physicsClientId=self.__client_id)
        self.__n_updates += 1

    def post_update(self):
        """Called after every physics step."""
        for plugin in self.__plugins:
            plugin.post_physics_update(self, self.time_step)

    def update(self):
        """Performs one complete update, consisting of pre-, physics- and post update."""
        self.pre_update()
        self.physics_update()
        self.post_update()


    def reset(self):
        """Resets all bodies in the simulation to their initial state."""
        for body in self.bodies.values():
            body.reset()
        for plugin in self.__plugins:
            plugin.reset(self)

    def register_object(self, obj, name_override=None):
        """Registers an object with the simulator.
        Unless a specific name is given, the simulator will automatically assign one to the object.
        If the specific name is already taken an exception will be raised.

        :param obj:           Object to register with the simulator.
        :type  obj:           iai_bullet_sim.rigid_body.RigidBody, iai_bullet_sim.multibody.MultiBody
        :param name_override: Name to assign to the object.
        :type  obj:           str, NoneType
        """
        if name_override is None:
            if isinstance(obj, MultiBody):
                base_link, bodyId = pb.getBodyInfo(obj.bId(), physicsClientId=self.__client_id)
            elif isinstance(obj, RigidBody):
                bodyId = obj.type
            counter = 0
            bodyName = bodyId
            while bodyId in self.bodies:
                bodyId = '{}.{}'.format(bodyName, counter)
                counter += 1

            self.bodies[bodyId] = obj
            self.__bId_IdMap[obj.bId()] = bodyId
            return bodyId
        else:
            if name_override in self.bodies:
                raise Exception('Id "{}" is already taken.'.format(name_override))

            self.bodies[name_override] = obj
            self.__bId_IdMap[obj.bId()] = name_override
            return name_override

    def register_deletion_cb(self, bodyId, cb):
        """Registers a callback function which is called when the specified object is deleted.

        :param bodyId: Body to listen for
        :type  bodyId: str
        :param cb: Callback to be called. Signature f(BasicSimulator, str, RigidBody/MultiBody)
        :tyoe  cb: function
        """
        if bodyId not in self.bodies:
            raise Exception('Can not register deletion callback for unknown body {}'.format(bodyId))

        if bodyId not in self.deletion_cbs:
            self.deletion_cbs[bodyId] = set()
        self.deletion_cbs[bodyId].add(cb)

    def deregister_deletion_cb(self, bodyId, cb):
        """Deregisters a callback function which is called when the specified object is deleted.

        :param bodyId: Body to listen for
        :type  bodyId: str
        :param cb: Callback to be called. Signature f(BasicSimulator, str, RigidBody/MultiBody)
        :tyoe  cb: function
        """
        if bodyId in self.deletion_cbs:
            self.deletion_cbs[bodyId].remove(cb)

    def register_plugin(self, plugin):
        """Registers a plugin with the simulator.

        :type plugin: SimulatorPlugin
        """
        self.__plugins.add(plugin)

    def deregister_plugin(self, plugin):
        """Removes a plugin from the simulator's registry.

        :type plugin: SimulatorPlugin
        """
        self.__plugins.remove(plugin)

    def has_plugin_of_type(self, clazz):
        """Returns True if at least one of the registered classes matches the given type.

        :rtype: bool
        """
        for p in self.__plugins:
            if isinstance(p, clazz):
                return True
        return False

    def get_plugin_of_type(self, clazz):
        """Returns a plugin of the given type if such a plugin is registered.

        :rtype: SimulatorPlugin, NoneType
        """
        for p in self.__plugins:
            if isinstance(p, clazz):
                return p
        return None

    def load_mesh(self, dae_path, pos=[0,0,0], rot=[0,0,0,1], name_override=None, collision_path=None):
        path = res_pkg_path(dae_path)

        name = dae_path[dae_path.rfind('/'):dae_path.rfind('.')] if '/' in dae_path else dae_path[:dae_path.rfind('.')]
        urdf_path = '{}{}.urdf'.format(tempfile.gettempdir(), name)
        f = open(urdf_path, 'w')
        f.write(self.__mesh_template.render(object_name=name, 
                                            mesh_path=dae_path, 
                                            collision_path=collision_path))
        f.close()
        print('Generated urdf: {}'.format(urdf_path))
        new_mb = self.load_urdf(urdf_path, pos, rot, name_override=name_override)
        new_mb.urdf_file = dae_path
        return new_mb

    def load_urdf(self, urdf_path, pos=[0,0,0], rot=[0,0,0,1], joint_driver=JointDriver(), useFixedBase=0, name_override=None):
        """Loads an Object from a URDF and registers it with this simulator.

        :param urdf_path:     Path of the file as local or global path, or as ROS package URI.
        :type  urdf_path:     str
        :param pos:           Position to create the object at.
        :type  pos:           list
        :param rot:           Rotation to create the object with.
        :type  rot:           list
        :param joint_driver:  Custom joint driver for custom joint behavior.
        :type  joint_driver:  iai_bullet_sim.multibody.JointDriver
        :param useFixedBase:  Should the base of the object be fixed in space?
        :type  useFixedBase:  int, bool
        :param name_override: Custom name to assign to this object during registration.
        :type  name_override: str, NoneType
        :rtype: iai_bullet_sim.multibody.MultiBody
        """
        res_urdf_path = res_pkg_path(urdf_path)
        #print('Simulator: {}'.format(res_urdf_path))

        new_body = MultiBody(self, pb.loadURDF(res_urdf_path,
                                               pos,
                                               rot,
                                               0,              # MAXIMAL COORDINATES, DO NOT TOUCH!
                                               useFixedBase,
                                               flags=pb.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT, physicsClientId=self.__client_id), self.__gen_next_color(), pos, rot, joint_driver, urdf_path)


        self.register_object(new_body, name_override)
        #print('Created new multibody with id {}'.format(bodyId))
        return new_body


    def create_sphere(self, radius=0.5, pos=[0,0,0], rot=[0,0,0,1], mass=1, color=None, name_override=None):
        """Creates and registers a spherical rigid body.

        :param radius:        Sphere's radius
        :type  radius:		  float
        :param pos:           Position to create the object at
        :type  pos:	          list
        :param rot:           Rotation to create the object with
        :type  rot:	          list
        :param mass:          Mass of the object
        :type  mass:		  float
        :param color:         Color of the object in RGBA
        :type  color:		  list
        :param name_override: Name for the object to be registered with.
        :type  name_override: str, NoneType
        :rtype: iai_bullet_sim.rigid_body.RigidBody
        """
        return self.create_object(BULLET_GEOM_TYPES[pb.GEOM_SPHERE], radius=radius, pos=pos, rot=rot, mass=mass, color=color, name_override=name_override)

    def create_box(self, extents=[1]*3, pos=[0,0,0], rot=[0,0,0,1], mass=1, color=None, name_override=None):
        """Creates and registers a box shaped rigid body.

        :param extents:       Edge lengths of the box
        :type  extents:		  list
        :param pos:           Position to create the object at
        :type  pos:           list
        :param rot:           Rotation to create the object with
        :type  rot:           list
        :param mass:          Mass of the object
        :type  mass:          float
        :param color:         Color of the object
        :type  color:         list
        :param name_override: Name for the object to be registered with.
        :type  name_override: str, NoneType
        :rtype: iai_bullet_sim.rigid_body.RigidBody
        """
        return self.create_object(BULLET_GEOM_TYPES[pb.GEOM_BOX], extents=extents, pos=pos, rot=rot, mass=mass, color=color, name_override=name_override)

    def create_cylinder(self, radius=0.5, height=1, pos=[0,0,0], rot=[0,0,0,1], mass=1, color=None, name_override=None):
        """Creates and registers a cylindrical rigid body.

        :param radius:        Cylinder's radius
        :type  radius:        float
        :param height:        Height of the cylinder
        :type  height:        float
        :param pos:           Position to create the object at
        :type  pos:           list
        :param rot:           Rotation to create the object with
        :type  rot:           list
        :param mass:          Mass of the object
        :type  mass:          float
        :param color:         Color of the object as RGBA
        :type  color:         list
        :param name_override: Name for the object to be registered with.
        :type  name_override: str, NoneType
        :rtype: iai_bullet_sim.rigid_body.RigidBody
        """
        return self.create_object(BULLET_GEOM_TYPES[pb.GEOM_CYLINDER], radius=radius, height=height, pos=pos, rot=rot, mass=mass, color=color, name_override=name_override)

    def create_capsule(self, radius=0.5, height=1, pos=[0,0,0], rot=[0,0,0,1], mass=1, color=None, name_override=None):
        """Creates and registers a capsule shaped rigid body.

        :param radius:        Capsule's radius
        :type  radius:        float
        :param height:        Height of the capsule
        :type  height:        float
        :param pos:           Position to create the object at
        :type  pos:           list
        :param rot:           Rotation to create the object with
        :type  rot:           list
        :param mass:          Mass of the object
        :type  mass:          float
        :param color:         Color of the object as RGBA
        :type  color:         list
        :param name_override: Name for the object to be registered with.
        :type  name_override: str, NoneType
        :rtype: iai_bullet_sim.rigid_body.RigidBody
        """
        return self.create_object(BULLET_GEOM_TYPES[pb.GEOM_CAPSULE], radius=radius, height=height, pos=pos, rot=rot, mass=mass, color=color, name_override=name_override)


    def create_object(self, geom_type, extents=[1,1,1], radius=0.5, height=1, pos=[0,0,0], rot=[0,0,0,1], mass=1, color=None, name_override=None):
        """Creates and registers a rigid body.

        :param geom_type:     Type of object. box | sphere | cylinder | capsule
        :type  geom_type:     str
        :param extents:       Edge lengths of the box
        :type  extents:       list
        :param radius:        Radius for spheres, cylinders and capsules
        :type  radius:        float
        :param height:        Height of the cylinder and capsule
        :type  height:        float
        :param pos:           Position to create the object at
        :type  pos:           list
        :param rot:           Rotation to create the object with
        :type  rot:           list
        :param mass:          Mass of the object
        :type  mass:          float
        :param color:         Color of the object as RGBA
        :type  color:         list, NoneType
        :param name_override: Name for the object to be registered with.
        :type  name_override: str, NoneType
        :rtype: iai_bullet_sim.rigid_body.RigidBody
        """
        if geom_type not in GEOM_TYPES:
            raise Exception('Unknown geometry type "{}". Options are: {}'.format(geom_type, ', '.join(GEOM_TYPES.keys())))

        if color is None:
            color = self.__gen_next_color()

        new_body = RigidBody(self,
                             pb.createRigidBody(GEOM_TYPES[geom_type], radius, [0.5 * x for x in extents], height, mass, pos, rot, color, physicsClientId=self.__client_id),
                             geom_type, color, pos, rot, extents, radius, height, mass)
        self.register_object(new_body, name_override)
        #print('Created new rigid body with id {}'.format(bodyId))
        return new_body


    def get_body_id(self, bulletId):
        """Returns the name of the object associated with a specific Bullet Id.

        :type bulletId: long
        :rtype: str, NoneType
        """
        if bulletId in self.__bId_IdMap:
            return self.__bId_IdMap[bulletId]
        return None

    def get_body(self, bodyId):
        """Returns the object associated with a name.

        :type bodyId: str
        :rtype: iai_bullet_sim.multibody.MultiBody, iai_bullet_sim.rigid_body.RigidBody, NoneType
        """
        if bodyId in self.bodies:
            return self.bodies[bodyId]
        return None


    def delete_body(self, bodyId):
        """
        Removes body associated with the given Id from the simulation. Returns True, if body was deleted.

        :param bodyId: Id of body to be deleted
        :type  bodyId: string
        :rtype: bool
        """
        if bodyId in self.bodies:
            body = self.bodies[bodyId]
            if bodyId in self.deletion_cbs:
                for cb in self.deletion_cbs[bodyId]:
                    cb(self, bodyId, body)
                del self.deletion_cbs[bodyId]
            pb.removeBody(body.bId(), self.__client_id)
            del self.__bId_IdMap[body.bId()]
            del self.bodies[bodyId]
            return True
        return False

    def delete_constraint(self, constraintId):
        if constraintId in self.constraints:
            constraint = self.constraints[constraintId]
            if constraintId in self.constraint_deletion_cbs:
                for cb in self.constraint_deletion_cbs[constraintId]:
                    cb(self, constraintId, constraint)
                del self.constraint_deletion_cbs[constraintId]
            pb.removeConstraint(constraint.bId(), self.__client_id)
            del self.__cId_IdMap[constraint.bId()]
            del self.constraints[constraintId]
            return True
        return False


    def create_constraint_global(self, parentBody, childBody, jointType='fixed',
                                 jointPosition=[0,0,0], jointAxis=[1,0,0],
                                 parentLink=None, childLink=None, name_override=None):
        parent_pose = parentBody.get_link_state(parentLink) if parentLink is not None else parentBody.pose()
        if childBody is not None:
            child_pose = childBody.get_link_state(childLink) if childLink is not None else childBody.pose()
        else:
            child_pose = Frame((0, 0, 0), (0, 0, 0, 1))
        inv_pp_pos, inv_pp_rot = pb.invertTransform(parent_pose.position, parent_pose.quaternion)
        inv_cp_pos, inv_cp_rot = pb.invertTransform(child_pose.position,  child_pose.quaternion)

        ZERO_VEC = (0,0,0)
        ZERO_ROT = (0,0,0,1)
        pjp, pjo = pb.multiplyTransforms(inv_pp_pos, inv_pp_rot, jointPosition, ZERO_ROT)
        cjp, cjo = pb.multiplyTransforms(inv_cp_pos, inv_cp_rot, jointPosition, ZERO_ROT)
        cja,   _ = pb.multiplyTransforms(  ZERO_VEC, inv_cp_rot,     jointAxis, ZERO_ROT)

        return self.create_constraint_local(parentBody, childBody, jointType, parentLink, childLink,
                                            cja, pjp, cjp, pjo, cjo, name_override)


    def create_constraint_local(self, parentBody, childBody, jointType='fixed',
                                parentLink=None, childLink=None, jointAxis=[1,0,0],
                                parentJointPosition=[0,0,0], childJointPosition=[0,0,0],
                                parentJointOrientation=[0,0,0,1], childJointOrientation=[0,0,0,1], name_override=None):
        if name_override is None:
            counter = 0
            constraintName = 'constraint_{}'.format(jointType.lower())
            constraintId   = constraintName
            while constraintId in self.bodies:
                constraintId = '{}.{}'.format(bodyName, counter)
                counter += 1
        else:
            if name_override in self.constraints:
                raise Exception('Constraint Id "{}" is already taken.'.format(name_override))

            constraintId = name_override

        parent_bid  = parentBody.bId()
        parent_link = parentBody.get_link_index(parentLink) if parentLink is not None else -1
        
        child_bid  = childBody.bId() if childBody is not None else -1
        child_link = childBody.get_link_index(childLink) if childLink is not None else -1

        if jointType not in self.__joint_types:
            raise Exception('Unknown joint type "{}". Supported types are: {}'.format(jointType, ', '.join(self.__joint_types.keys())))
        type = self.__joint_types[jointType]

        bulletId = pb.createConstraint(parent_bid, parent_link, child_bid, child_link, type, axis, 
                                       parentJointPosition, childJointPosition, 
                                       parentJointOrientation, childJointOrientation, physicsClientId=self.__client_id)
        constraint = Constraint(self, bulletId, jointType, parentBody, childBody,
                                      parentJointPosition, parentJointOrientation,
                                      childJointPosition,  childJointOrientation,
                                      jointAxis, parentLink, childLink)
        self.constraints[constraintId] = constraint
        self.__cId_IdMap[bulletId]     = constraintId
        return constraint


    # @profile
    def get_overlapping(self, aabb, filter=set()):
        """Returns all objects overlapping the given bounding box.

        :param aabb:   Axis aligned bounding box to check against.
        :type  aabb:   AABB
        :param filter: All objects in this set get filtered from the results.
        :type  filter: set
        :rtype: list
        """
        raw_overlap = pb.getOverlappingObjects(vec3_to_list(aabb.min), vec3_to_list(aabb.max), physicsClientId=self.__client_id)
        if raw_overlap is None:
            return []

        return [self.__get_obj_link_tuple(bulletId, linkIdx) for bulletId, linkIdx in raw_overlap if self.bodies[self.__bId_IdMap[bulletId]] not in filter]

    # @profile
    def get_contacts(self, bodyA=None, bodyB=None, linkA=None, linkB=None):
        """Returns all contacts generated during the last physics step.

        :param bodyA: All returned contacts will involve this object.
        :type  bodyA: iai_bullet_sim.rigid_body.RigidBody, iai_bullet_sim.multibody.MultiBody
        :param bodyB: All returned contacts will only be between this object and bodyA.
        :type  bodyB: iai_bullet_sim.rigid_body.RigidBody, iai_bullet_sim.multibody.MultiBody
        :param linkA: All contact will involve this link of bodyA.
        :type  linkA: str, NoneType
        :param linkB: All returned will involve this link of bodyB
        :type  linkB: str, NoneType
        :rtype: list
        """
        bulletA = bodyA.bId() if bodyA != None else -1
        bulletB = bodyB.bId() if bodyB != None else -1
        bulletLA = bodyA.link_index_map[linkA] if bodyA != None and linkA != None and isinstance(bodyA, MultiBody) else -1
        bulletLB = bodyB.link_index_map[linkB] if bodyB != None and linkB != None and isinstance(bodyB, MultiBody) else -1
        contacts = []
        if bulletLA == -1 and bulletLB == -1:
            contacts = pb.getContactPoints(bulletA, bulletB, physicsClientId=self.__client_id)
        elif bulletLA != -1 and bulletLB == -1:
            contacts = pb.getContactPoints(bulletA, bulletB, linkIndexA=bulletLA, physicsClientId=self.__client_id)
        elif bulletLA == -1 and bulletLB != -1:
            contacts = pb.getContactPoints(bulletA, bulletB, linkIndexB=bulletLB, physicsClientId=self.__client_id)
        else:
            contacts = pb.getContactPoints(bulletA, bulletB, bulletLA, bulletLB, physicsClientId=self.__client_id)
        return [self.__create_contact_point(c) for c in contacts]


    # @profile
    def get_closest_points(self, bodyA, bodyB, linkA=None, linkB=None, dist=0.2):
        """Returns all the closest points between two objects.

        :param bodyA: First body.
        :type  bodyA: iai_bullet_sim.rigid_body.RigidBody, iai_bullet_sim.multibody.MultiBody
        :param bodyB: Second body.
        :type  bodyB: iai_bullet_sim.rigid_body.RigidBody, iai_bullet_sim.multibody.MultiBody
        :param linkA: Closest point will be on this link of bodyA.
        :type  linkA: str, NoneType
        :param linkB: Closest point will be on this link of bodyB.
        :type  linkB: str, NoneType
        :rtype: list
        """
        bulletA = bodyA.bId() if bodyA != None else -1
        bulletB = bodyB.bId() if bodyB != None else -1
        bulletLA = bodyA.link_index_map[linkA] if bodyA != None and linkA != None and isinstance(bodyA, MultiBody) else -1
        bulletLB = bodyB.link_index_map[linkB] if bodyB != None and linkB != None and isinstance(bodyB, MultiBody) else -1
        contacts = []
        if bulletLA == -1 and bulletLB == -1:
            contacts = pb.getClosestPoints(bulletA, bulletB, distance=dist, physicsClientId=self.__client_id)
        elif bulletLA != -1 and bulletLB == -1:
            contacts = pb.getClosestPoints(bulletA, bulletB, linkIndexA=bulletLA, distance=dist, physicsClientId=self.__client_id)
        elif bulletLA == -1 and bulletLB != -1:
            contacts = pb.getClosestPoints(bulletA, bulletB, linkIndexB=bulletLB, distance=dist, physicsClientId=self.__client_id)
        else:
            contacts = pb.getClosestPoints(bulletA, bulletB, dist, bulletLA, bulletLB, physicsClientId=self.__client_id)
        return [self.__create_contact_point(c) for c in contacts]

    def load_world(self, world_dict):
        """Loads a world configuration from a dictionary.

        :param world_dict: World configuration
        :type  world_dict: dict
        """
        driver_registry = {}
        if 'objects' in world_dict:
            if type(world_dict['objects']) != list:
                raise Exception('Field "objects" in world dictionary needs to be of type list.')

            for od in world_dict['objects']:
                otype  = od['type']
                name  = od['name']
                i_pos = od['initial_pose']['position']
                i_rot = od['initial_pose']['rotation']

                if otype == 'multibody':
                    urdf_path = od['urdf_path']
                    fixed_base = od['fixed_base']
                    initial_joint_state = od['initial_joint_state']

                    if 'joint_driver' in od:
                        driver_dict = od['joint_driver']
                        driver_class = driver_dict['driver_type']
                        if driver_class not in driver_registry:
                            if driver_class[:8] == '<class \'' and driver_class[-2:] == '\'>':
                                driver_registry[driver_class] = import_class(driver_class[8:-2])
                            else:
                                raise Exception('Driver type "{}" does not match the pattern "<class \'TYPE\'>"'.format(driver_class))
                        joint_driver = driver_registry[driver_class].factory(driver_dict)
                    else:
                        joint_driver = JointDriver()

                    if urdf[:-5].lower() == '.urdf': 
                        new_obj = self.load_urdf(urdf_path,
                                                 i_pos,
                                                 i_rot, joint_driver=joint_driver, useFixedBase=fixed_base, name_override=name)
                        new_obj.set_joint_positions(initial_joint_state, True)
                    else:
                        new_obj = self.load_mesh(urdf_path, i_pos, i_rot, name_override=name)
                    for s in od['sensors']:
                        new_obj.enable_joint_sensor(s, True)
                elif otype == 'rigid_body':
                    self.create_object(od['geom_type'], od['extents'], od['radius'], od['height'], i_pos, i_rot, od['mass'], od['color'], name)
                else:
                    raise Exception('Unknown object type "{}"'.format(otype))
        if 'constraints' in world_dict:
            for cd in world_dict['constraints']:
                if cd['parent'] not in self.bodies:
                    raise Exception('Parent body "{}" for constraint "{}" cannot be found.'.format(cd['parent'], cd['name']))
                if cd['child'] is not None and cd['child'] not in self.bodies:
                    raise Exception('Child body "{}" for constraint "{}" cannot be found.'.format(cd['parent'], cd['name']))

                parentBody = self.bodies[cd['parent']]
                childBody  = self.bodies[cd['child']] if cd['child'] is not None else None

                self.create_constraint_local(parentBody, childBody, cd['type'], cd['parent_link'], cd['child_link'],
                                             cd['axis'], cd['parent_pose']['position'], cd['child_pose']['position'],
                                             cd['parent_pose']['rotation'], cd['child_pose']['rotation'], cd['name'])


    def save_world(self, use_current_state_as_init=False):
        """Serializes the positional state of the simulation to a dictionary.

        :param use_current_state_as_init: Should the current state, or the initial state be serialized.
        :type  use_current_state_as_init: bool
        :rtype: dict
        """
        out = {'objects': [], 'constraints': []}

        for bname, b in self.bodies.items():
            if isinstance(b, MultiBody):
                in_pos = b.pose().position if use_current_state_as_init else b.initial_pos
                in_rot = b.pose().quaternion if use_current_state_as_init else b.initial_rot
                if use_current_state_as_init:
                    in_js = {j: p.position for j, p in b.joint_state().items()}
                else:
                    in_js = b.initial_joint_state

                driver_dict = {'driver_type': str(type(b.joint_driver))}
                driver_dict.update(b.joint_driver.to_dict())

                od = {'name': bname,
                      'type': 'multibody',
                      'initial_pose': {
                        'position': list(in_pos),
                        'rotation': list(in_rot)},
                      'urdf_path': b.urdf_file,
                      'initial_joint_state': in_js,
                      'fixed_base': True,
                      'sensors': list(b.joint_sensors),
                      'joint_driver': driver_dict} # TODO: Update this!
                out['objects'].append(od)
            elif isinstance(b, RigidBody):
                in_pos = b.pose().position if use_current_state_as_init else b.initial_pos
                in_rot = b.pose().quaternion if use_current_state_as_init else b.initial_rot

                od = {'name': bname,
                      'type': 'rigid_body',
                      'geom_type': b.type,
                      'initial_pose': {
                        'position': list(in_pos),
                        'rotation': list(in_rot)},
                      'color': list(b.color),
                      'mass': b.mass,
                      'extents': list(b.extents),
                      'radius': b.radius,
                      'height': b.height} # TODO: Update this!
                out['objects'].append(od)
            else:
                raise Exception('Can not serialize type "{}"'.format(str(type(b))))


        for cname, c in self.constraints.items():
            parent_name = self.__bId_IdMap[c.parent.bId()]
            child_name  = self.__bId_IdMap[c.child.bId()] if c.child is not None else None

            cd = {'name': cname,
                  'type': c.type,
                  'parent': parent_name,
                  'child' : child_name,
                  'parent_link': c.parent_link,
                  'child_link' : c.child_link,
                  'axis' : list(c.axis),
                  'parent_pose': {
                    'position': list(c.parent_pos),
                    'rotation': list(c.parent_rot)},
                  'child_pose': {
                    'position': list(c.child_pos),
                    'rotation': list(c.child_rot)}}
            out['constraints'].append(cd)
        return out


    def load_simulator(self, config_dict):
        """Loads a simulator configuration from a dictionary.

        :param config_dict:     Simulator configuration.
        :type  config_dict:     dict
        """
        if 'tick_rate' in config_dict:
            self.set_tick_rate(config_dict['tick_rate'])

        if 'gravity' in config_dict:
            self.set_gravity(config_dict['gravity'])

        if 'world' in config_dict:
            self.load_world(config_dict['world'])

        if 'plugins' in config_dict:

            for plugin_dict in config_dict['plugins']:
                plugin_registry = {}
                plugin = plugin_dict['plugin_type']
                if plugin not in plugin_registry:
                    if plugin[:8] == '<class \'' and plugin[-2:] == '\'>':
                        plugin_registry[plugin] = import_class(plugin[8:-2])
                    else:
                        raise Exception('Plugin type "{}" does not match the pattern "<class \'TYPE\'>"'.format(plugin))

                self.register_plugin(plugin_registry[plugin].factory(self, plugin_dict))


    def save_simulator(self, use_current_state_as_init=False):
        """Saves the simulator's state to a dictionary.

        :param use_current_state_as_init: Should the current state, or the initial state be serialized.
        :type  use_current_state_as_init: bool
        :rtype: dict
        """
        out = {'tick_rate': self.tick_rate,
               'gravity': self.gravity,
               'world': self.save_world(use_current_state_as_init),
               'plugins': []}

        for plugin in self.__plugins:
            if 'factory' in dir(plugin) and callable(getattr(plugin, 'factory')):
                pdict = {'plugin_type': str(type(plugin))}
                pdict.update(plugin.to_dict(self))
                out['plugins'].append(pdict)
        return out


    def __create_contact_point(self, bcp):
        """Internal. Turns a bullet contact point into a ContactPoint."""
        bodyA, linkA = self.__get_obj_link_tuple(bcp[1], bcp[3])
        bodyB, linkB = self.__get_obj_link_tuple(bcp[2], bcp[4])
        return ContactPoint(bodyA,          # Body A
                            bodyB,          # Body B
                            linkA,          # Link of A
                            linkB,          # Link of B
                            Vector3(*bcp[5]), # Point on A
                            Vector3(*bcp[6]), # Point on B
                            Vector3(*bcp[7]), # Normal from B to A
                            bcp[8],           # Distance
                            bcp[9])           # Normal force

    def __get_obj_link_tuple(self, bulletId, linkIdx):
        """Internal. Turns a bullet id and a link index into a tuple of the corresponding object and the link's name."""
        body = self.bodies[self.__bId_IdMap[bulletId]]
        link = body.index_link_map[linkIdx] if isinstance(body, MultiBody) else None
        return (body, link)


class SimulatorPlugin(object):
    """Superclass for simulator plugins.
    Implement a method class method "factory(cls, simulator, init_dict)" as factory method for your class.
    """
    def __init__(self, name):
        super(SimulatorPlugin, self).__init__()
        self.__name = name

    def pre_physics_update(self, simulator, deltaT):
        """Implements pre physics step behavior.

        :type simulator: BasicSimulator
        :type deltaT: float
        """
        pass

    def post_physics_update(self, simulator, deltaT):
        """Implements post physics step behavior.

        :type simulator: BasicSimulator
        :type deltaT: float
        """
        pass

    def disable(self, simulator):
        """Stops the execution of this plugin.

        :type simulator: BasicSimulator
        """
        pass

    def __str__(self):
        return self.__name

    def to_dict(self, simulator):
        """Serializes this plugin to a dictionary.

        :type simulator: BasicSimulator
        :rtype: dict
        """
        raise (NotImplementedError)

    def reset(self, simulator):
        """Implements reset behavior.

        :type simulator: BasicSimulator
        :type deltaT: float
        """
        pass