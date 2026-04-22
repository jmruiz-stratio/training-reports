<?php
defined('MOODLE_INTERNAL') || die();

// Sin capabilities propias: las funciones exigen solo que el token tenga
// acceso al servicio externo 'stratiorep'. El acceso se controla en
// db/services.php con restrictedusers=1.
$capabilities = [];
