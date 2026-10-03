/* Written by mount-editor.html — coordinates are metres in the truck's own
   space. x = left/right, y = height above the floor, z = negative toward the
   forks. yawDeg: 180 forward, 0 astern, -90 left, 90 right.

   NOTE: yaw values below are your editor values with +180 applied. The editor
   was rendering with an extra half-turn that the site did not, so what looked
   right in the tool came out reversed on the page. Both now use the convention
   documented above, so anything you save from here on drops straight in. */
window.__RAMS_MOUNTS = {
  scale: 0.130,
  pitchDeg: 25,
  units: [
    {key:"fr", label:"FRONT RIGHT", x:0.510, y:2.155, z:0.200, yawDeg:163},
    {key:"fl", label:"FRONT LEFT", x:-0.495, y:2.155, z:0.200, yawDeg:196},
    {key:"sl", label:"SIDE LEFT", x:-0.555, y:2.225, z:0.650, yawDeg:-90},
    {key:"sr", label:"SIDE RIGHT", x:0.555, y:2.225, z:0.655, yawDeg:90},
    {key:"rr", label:"REAR", x:0.000, y:2.235, z:1.085, yawDeg:0}
  ]
};
