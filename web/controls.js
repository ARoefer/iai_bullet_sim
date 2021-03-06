
String.prototype.format = function () {
  var i = 0, args = arguments;
  return this.replace(/{}/g, function () {
    return typeof args[i] != 'undefined' ? args[i++] : '';
  });
};

var objects = {multi: {}, rigid: {}};
var simState = {running: false};

var empty_request = new ROSLIB.ServiceRequest({});

$(function() {

  $('.accordion').click(accordion_handler('.action', false));

  $('#form_rigid_body').on('submit', function(event) {
    // Stop the form from submitting since we’re handling that with AJAX.
    event.preventDefault();
    const data = formToJSON(this.elements);

    console.log(data);

    var add_body_request = new ROSLIB.ServiceRequest({
      geom_type: data['geom_type'],
      extents: {x: parseFloat(data['x']), y: parseFloat(data['y']), z: parseFloat(data['z'])},
      height: parseFloat(data['z']),
      radius: parseFloat(data['radius']),
      pose: {position: {x: parseFloat(data['position_x']),
                        y: parseFloat(data['position_y']),
                        z: parseFloat(data['position_z'])},
            orientation: {x: 0,
                          y: 0,
                          z: 0,
                          w: 1}},
      mass: parseFloat(data['mass']),
      color: {r: 0, g: 0, b: 0, a: 0},
      name: data['name']
    });
    srv_add_rigid_body.callService(add_body_request, function(result) {
      process_feedback(result.success, result.error_msg);
      refresh_objects();
    });
  });

  $('#form_urdf').on('submit', function(event) {
    // Stop the form from submitting since we’re handling that with AJAX.
    event.preventDefault();
    const data = formToJSON(this.elements);

    console.log(data);

    var add_body_request = new ROSLIB.ServiceRequest({
      urdf_path: data['urdf_path'],
      fixed_base: false,
      pose: {position: {x: parseFloat(data['position_x']),
                        y: parseFloat(data['position_y']),
                        z: parseFloat(data['position_z'])},
            orientation: {x: 0,
                          y: 0,
                          z: 0,
                          w: 1}},
      name: ""
    });
    srv_add_urdf.callService(add_body_request, function(result) {
      process_feedback(result.success, result.error_msg);
      refresh_objects();
    });
  });

  $('#form_save_yaml').on('submit', function(event) {
    // Stop the form from submitting since we’re handling that with AJAX.
    event.preventDefault();
    const data = formToJSON(this.elements);

    var save_yaml_request = new ROSLIB.ServiceRequest({
      path: data['yaml_path'],
      use_current_as_initial: false
    });

    srv_save_to_yaml.callService(save_yaml_request, function(result) {
      if (result.success) {
        close_save_modal();
      } else {
        process_msg_feedback(result);
      }
    });
  });

  $('#form_save_rosparam').on('submit', function(event) {
    // Stop the form from submitting since we’re handling that with AJAX.
    event.preventDefault();
    const data = formToJSON(this.elements);

    var save_param_request = new ROSLIB.ServiceRequest({
      path: data['rosparam'],
      use_current_as_initial: false
    });

    srv_save_to_rosparam.callService(save_param_request, function(result) {
      if (result.success) {
        close_save_modal();
      } else {
        process_msg_feedback(result);
      }
    });
  });

  $('#form_gravity').on('submit', function(event) {
    // Stop the form from submitting since we’re handling that with AJAX.
    event.preventDefault();
    const data = formToJSON(this.elements);

    var set_gravity_request = new ROSLIB.ServiceRequest({
      gravity: {x: parseFloat(data['gravity_x']),
                y: parseFloat(data['gravity_y']),
                z: parseFloat(data['gravity_z'])}
    });

    srv_set_gravity.callService(set_gravity_request, process_msg_feedback);
  });

  srv_get_state.callService(empty_request, function(result) {
    simState.running = result.state == 1;
    refresh_simulator_state();
  });
});

// Connecting to ROS
// -----------------
var ros = new ROSLIB.Ros();
// If there is an error on the backend, an 'error' emit will be emitted.
ros.on('error', function(error) {
  $('.statusDisplay').hide();
  document.getElementById('error').style.display = 'block';
  console.log(error);
});
// Find out exactly when we made a connection.
ros.on('connection', function() {
  console.log('Connection made!');
  $('.statusDisplay').hide();
  document.getElementById('connected').style.display = 'block';
  refresh_objects();
});
ros.on('close', function() {
  console.log('Connection closed.');
  $('.statusDisplay').hide();
  document.getElementById('closed').style.display = 'block';
});
// Create a connection to the rosbridge WebSocket server.
ros.connect('ws://localhost:9097');


var srv_get_obj_ids = new ROSLIB.Service({
  ros: ros,
  name: '/get_object_ids',
  serviceType: 'iai_bullet_sim/GetObjectIds'
});

var srv_get_rigid_ids = new ROSLIB.Service({
  ros: ros,
  name: '/get_rigid_object_ids',
  serviceType: 'iai_bullet_sim/GetObjectIds'
});

var srv_get_multibody_ids = new ROSLIB.Service({
  ros: ros,
  name: '/get_multibody_ids',
  serviceType: 'iai_bullet_sim/GetObjectIds'
});

var srv_get_obj_joints = new ROSLIB.Service({
  ros: ros,
  name: '/get_joints',
  serviceType: 'iai_bullet_sim/GetJoints'
});

var srv_get_multibodies = new ROSLIB.Service({
  ros: ros,
  name: '/get_multibodies',
  serviceType: 'iai_bullet_sim/GetMultibodies'
});

var srv_get_rigidbodies = new ROSLIB.Service({
  ros: ros,
  name: '/get_rigidbodies',
  serviceType: 'iai_bullet_sim/GetRigidBodies'
});

var srv_add_rigid_body = new ROSLIB.Service({
  ros: ros,
  name: '/add_rigid_object',
  serviceType: 'iai_bullet_sim/AddRigidObject'
});

var srv_add_urdf = new ROSLIB.Service({
  ros: ros,
  name: '/add_urdf',
  serviceType: 'iai_bullet_sim/AddURDF'
});

var srv_add_controller = new ROSLIB.Service({
  ros: ros,
  name: '/add_controller',
  serviceType: 'iai_bullet_sim/SetController'
});

var srv_remove_controller = new ROSLIB.Service({
  ros: ros,
  name: '/remove_controller',
  serviceType: 'iai_bullet_sim/SetController'
});

var srv_set_joint_sensor = new ROSLIB.Service({
  ros: ros,
  name: '/set_joint_sensor',
  serviceType: 'iai_bullet_sim/SetJointSensor'
});

var srv_set_joint_state = new ROSLIB.Service({
  ros: ros,
  name: '/set_joint_state',
  serviceType: 'iai_bullet_sim/SetJointState'
});

var srv_set_pose = new ROSLIB.Service({
  ros: ros,
  name: '/set_object_pose',
  serviceType: 'iai_bullet_sim/SetObjectPose'
});

var srv_set_gravity = new ROSLIB.Service({
  ros: ros,
  name: '/set_gravity',
  serviceType: 'iai_bullet_sim/SetGravity'
});

var srv_save_to_yaml = new ROSLIB.Service({
  ros: ros,
  name: '/save_to_yaml',
  serviceType: 'iai_bullet_sim/SaveSimulator'
});

var srv_save_to_rosparam = new ROSLIB.Service({
  ros: ros,
  name: '/save_to_rosparam',
  serviceType: 'iai_bullet_sim/SaveSimulator'
});

var srv_reset_object = new ROSLIB.Service({ros: ros,
  name: '/reset_object',
  serviceType: 'iai_bullet_sim/ObjectId'
});

var srv_delete_object = new ROSLIB.Service({ros: ros,
  name: '/delete_object',
  serviceType: 'iai_bullet_sim/ObjectId'
});

var srv_reset = new ROSLIB.Service({ros: ros,
  name: '/reset',
  serviceType: 'iai_bullet_sim/Empty'
});

var srv_pause = new ROSLIB.Service({ros: ros,
  name: '/pause',
  serviceType: 'iai_bullet_sim/Empty'
});

var srv_run = new ROSLIB.Service({ros: ros,
  name: '/run',
  serviceType: 'iai_bullet_sim/Empty'
});

var srv_get_state = new ROSLIB.Service({ros: ros,
  name: '/get_simulator_state',
  serviceType: 'iai_bullet_sim/GetSimulatorState'
});

var srv_select_object = new ROSLIB.Service({ros: ros,
  name: '/select_object',
  serviceType: 'iai_bullet_sim/ObjectId'
});

var listener_selection = new ROSLIB.Topic({
  ros : ros,
  name : '/selected_object',
  messageType : 'std_msgs/String'
});

listener_selection.subscribe(function(message) {
  if (message.data != '') {
    var ref_id = 'ref_{}'.format(message.data);
    var accordion = document.getElementById(ref_id);
    if (accordion) {
      if (!accordion.classList.contains('active')) {
        console.log('Selected was externally changed to {}'.format(ref_id))
        accordion.click();
      }
    }
  }
});



function refresh_objects() {
  var body_request = new ROSLIB.ServiceRequest({});

  objects.multi = {}
  objects.rigid = {}

  console.log('Refreshing objects...')
  $('.objectReference').remove();
  srv_get_rigidbodies.callService(body_request, function(result) {
    console.log(result);
    for (var x in result.name) {
      objects.rigid[result.name[x]] = rigidMsg2RigidInternal(result.body[x]);
      var id = 'ref_{}'.format(result.name[x]);
      var form_id = 'form_{}'.format(result.name[x].replace('.','__'));
      $('#objectList').append(generate_rigidbody_accordion(id, result.name[x], form_id, objects.rigid[result.name[x]]));
      $('#{} input'.format(form_id)).prop('disabled', true);
      $('#{} select'.format(form_id)).prop('disabled', true);
      update_rigid_form(form_id);
      document.getElementById(id).onclick = accordion_handler('.objectReference', true);
    }
  });

  srv_get_multibodies.callService(body_request, function(result) {
    console.log(result);
    for (var x in result.name) {
      objects.multi[result.name[x]] = result.body[x];
      var id = 'ref_{}'.format(result.name[x]);
      var form_id = 'form_{}'.format(result.name[x].replace('.','__'));
      $('#objectList').append(generate_multibody_accordion(id, result.name[x], form_id, objects.multi[result.name[x]]));
      document.getElementById(id).onclick = accordion_handler('.objectReference', true);
    }
  });
}

function accordion_handler(filter, select_objects) {
  return function() {
    /* Toggle between adding and removing the active class
      to highlight the button that controls the panel */
      $('{}.accordion'.format(filter)).removeClass('active');

      /* Toggle between hiding and showing the active panel */
      var panel = this.nextElementSibling;
      if (panel.style.maxHeight) {
          panel.style.maxHeight = null;
          var select_request = new ROSLIB.ServiceRequest({
              object_id: ''
            });
            srv_select_object.callService(select_request, function(result) {
              process_msg_feedback(result);
            });
      } else {
          $(this).addClass('active');
          $('.panel{}'.format(filter)).css('max-height', '');
          panel.style.maxHeight = panel.scrollHeight + 'px';
          if (select_objects) {
            var select_request = new ROSLIB.ServiceRequest({
              object_id: this.id.slice(4)
            });
            srv_select_object.callService(select_request, function(result) {
              process_msg_feedback(result);
            });
          }
      }
  };
}



function rigidMsg2RigidInternal(msg) {
  var z_extent = msg.extents.z;
  if (msg.geom_type !== 'box') {
    z_extent = msg.height;
  }
  return {geom_type: msg.geom_type,
          extents: {x: msg.extents.x,
                    y: msg.extents.y,
                    z: z_extent},
          radius: msg.radius,
          mass: msg.mass,
          pose: {position: {x: msg.initial_pose.position.x,
                            y: msg.initial_pose.position.y,
                            z: msg.initial_pose.position.z},
                 orientation: {x: msg.initial_pose.orientation.x,
                               y: msg.initial_pose.orientation.y,
                               z: msg.initial_pose.orientation.z,
                               w: msg.initial_pose.orientation.w}},
          color: rgbToHex(msg.color.r, msg.color.g, msg.color.b)};
}

function process_feedback(success, msg) {
  if (success) {
      $('.errorDisplay').hide();
    } else {
      $('.errorDisplay').html(msg);
      $('.errorDisplay').show();
    }
}

function process_msg_feedback(result_msg) {
  process_feedback(result_msg.success, result_msg.error_msg);
}

function refresh_simulator_state() {
  var indicator = document.getElementById('run_indicator');
  if (simState.running) {
    indicator.classList.remove('fa-play');
    indicator.classList.add('fa-pause');
  } else {
    indicator.classList.remove('fa-pause');
    indicator.classList.add('fa-play');
  }
}

function toggle_run_mode() {
  if (simState.running) {
    srv_pause.callService(empty_request, function(result) {
      if (result.success) {
        simState.running = false;
        refresh_simulator_state();
      } else {
        process_msg_feedback(result);
      }
    });
  } else {
    srv_run.callService(empty_request, function(result) {
      if (result.success) {
        simState.running = true;
        refresh_simulator_state();
      } else {
        process_msg_feedback(result);
      }
    });
  }
}

function set_mode_pause() {
  srv_pause.callService(empty_request, process_msg_feedback);
}

function reset_simulator() {
  srv_reset.callService(empty_request, process_msg_feedback);
}

function toggle_joint_sensor(bodyId, joint) {
  var enable = objects.multi[bodyId].sensors.indexOf(joint) == -1;
  var set_sensor_request = new ROSLIB.ServiceRequest({
    object_id: bodyId,
    joint: joint,
    enable: enable
  });
  srv_set_joint_sensor.callService(set_sensor_request, function(result) {
    if (result.success) {
      if (enable) {
        objects.multi[bodyId].sensors.push(joint);
        $('#{}__{}'.format(bodyId, joint)).addClass('sensor');
      } else {
        objects.multi[bodyId].sensors.splice(objects.multi[bodyId].sensors.indexOf(joint), 1);
        $('#{}__{}'.format(bodyId, joint)).removeClass('sensor');
      }
    } else {
      process_feedback(result_msg.success, result_msg.error_msg);
    }
  });
}

function update_rigid_form(form_id) {
  var geom = document.getElementById(form_id).querySelector('#rigidGeom').value;
  if (geom === 'box') {
    $('#{} .sphereThings'.format(form_id)).hide();
    $('#{} .boxThings'.format(form_id)).show();
  } else if (geom === 'sphere') {
    $('#{} .boxThings'.format(form_id)).hide();
    $('#{} .sphereThings'.format(form_id)).show();
  } else if (geom === 'cylinder' || geom === 'capsule') {
    $('#{} .boxThings'.format(form_id)).hide();
    $('#{} .sphereThings'.format(form_id)).show();
    $('#{} .cylinderThings'.format(form_id)).show();
  }
}

/**
 * Retrieves input data from a form and returns it as a JSON object.
 * @param  {HTMLFormControlsCollection} elements  the form elements
 * @return {Object}                               form data as an object literal
 */
const formToJSON = elements => [].reduce.call(elements, (data, element) => {

  data[element.name] = element.value;
  return data;

}, {});


function handleFormSubmit(event) {
  // Stop the form from submitting since we’re handling that with AJAX.
  event.preventDefault();

  // TODO: Call our function to get the form data.
  const data = formToJSON(this.elements);

  console.log(data);
}

function reset_object(object_id) {
  var obj_id_request = new ROSLIB.ServiceRequest({
    object_id: object_id
  });
  srv_reset_object.callService(obj_id_request, function(result) {
    process_feedback(result.success, result.error_msg);
  });
}

function delete_object(object_id) {
  promptConfirm('Delete {}?'.format(object_id), function() {
    var obj_id_request = new ROSLIB.ServiceRequest({
      object_id: object_id
    });
    srv_delete_object.callService(obj_id_request, function(result) {
      process_feedback(result.success, result.error_msg);
      if (result.success) {
        var btn = document.getElementById('ref_{}'.format(object_id));
        btn.nextElementSibling.remove();
        btn.remove();
      }
    });
  }, null);
}

function promptConfirm(what, fconfirm, fcancel) {
  $('#confirmWhat').html(what);
  $('#btnConfirm').click(function() {fconfirm(); $('#confirmationModal').hide();})
  if (fcancel) {
    $('#btnCancelConfirm').click(function() {fcancel(); $('#confirmationModal').hide();})
  } else {
    $('#btnCancelConfirm').click(function() {$('#confirmationModal').hide();})
  }
  $('#confirmationModal').show();
}

function open_save_modal() {
  $('#saveModal').show();
}

function close_save_modal() {
  $('#saveModal').hide();
}

function openTab(event, tabName) {
  $('.tabcontent').hide();
  $('.tablinks').removeClass('active');
  document.getElementById(tabName).style.display = 'block';
  event.currentTarget.className += 'active';
}

function componentToHex(c) {
    var hex = c.toString(16);
    return hex.length == 1 ? "0" + hex : hex;
}

function rgbToHex(r, g, b) {
    return "#" + componentToHex(Math.round(Math.abs(r * 255))) + componentToHex(Math.round(Math.abs(g * 255))) + componentToHex(Math.round(Math.abs(b * 255)));
}

function hexToRgb(hex) {
    var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}
