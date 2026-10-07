-- Datos 100% SINTÉTICOS para pruebas (no son personas reales).
insert into auth.users(id,email,encrypted_password,email_confirmed_at) values
 ('a0000000-0000-0000-0000-000000000001','admin@prueba.test',extensions.crypt('Admin-12345',extensions.gen_salt('bf')),now()),
 ('a0000000-0000-0000-0000-000000000002','deleg@prueba.test',extensions.crypt('Deleg-12345',extensions.gen_salt('bf')),now()),
 ('a0000000-0000-0000-0000-000000000003','lector@prueba.test',extensions.crypt('Lector-12345',extensions.gen_salt('bf')),now()),
 ('a0000000-0000-0000-0000-000000000004','captura@prueba.test',extensions.crypt('Captura-1234',extensions.gen_salt('bf')),now()),
 ('a0000000-0000-0000-0000-000000000005','soloinicio@prueba.test',extensions.crypt('Inicio-12345',extensions.gen_salt('bf')),now()),
 ('a0000000-0000-0000-0000-000000000006','baja@prueba.test',extensions.crypt('Baja-123456',extensions.gen_salt('bf')),now());

insert into public.app_profiles(user_id,email,display_name,role,status) values
 ('a0000000-0000-0000-0000-000000000001','admin@prueba.test','Admin','admin','active'),
 ('a0000000-0000-0000-0000-000000000002','deleg@prueba.test','Delegado','collaborator','active'),
 ('a0000000-0000-0000-0000-000000000003','lector@prueba.test','Lector','collaborator','active'),
 ('a0000000-0000-0000-0000-000000000004','captura@prueba.test','Captura','collaborator','active'),
 ('a0000000-0000-0000-0000-000000000005','soloinicio@prueba.test','Solo inicio','collaborator','active'),
 ('a0000000-0000-0000-0000-000000000006','baja@prueba.test','De baja','collaborator','disabled');

-- Delegado: ve personas y administra usuarios (view/create/edit/delete) + equipos (view/edit)
insert into public.app_permissions(user_id,module_key,can_view,can_create,can_edit,can_delete,can_export) values
 ('a0000000-0000-0000-0000-000000000002','inicio',true,false,false,false,false),
 ('a0000000-0000-0000-0000-000000000002','personas',true,false,false,false,false),
 ('a0000000-0000-0000-0000-000000000002','usuarios',true,true,true,true,false),
 ('a0000000-0000-0000-0000-000000000002','dispositivos',true,false,true,false,false),
 ('a0000000-0000-0000-0000-000000000003','inicio',true,false,false,false,false),
 ('a0000000-0000-0000-0000-000000000003','personas',true,false,false,false,true),
 ('a0000000-0000-0000-0000-000000000004','inicio',true,false,false,false,false),
 ('a0000000-0000-0000-0000-000000000004','personas',true,true,false,false,false),
 ('a0000000-0000-0000-0000-000000000005','inicio',true,false,false,false,false),
 ('a0000000-0000-0000-0000-000000000006','personas',true,true,true,true,true);

insert into public.app_devices(user_id,device_id,authorized) values
 ('a0000000-0000-0000-0000-000000000003','dev-lector-ok',true),
 ('a0000000-0000-0000-0000-000000000003','dev-lector-pend',false);

insert into public.personas(id_persona,id_persona_maestro,nombre,sexo,edad,escolaridad,carrera,institucion,municipio,vinculacion,fecha_registro,anio,estatus_vinculacion) values
 ('I-00001-00001','PER-0001','PERSONA PRUEBA UNO','Femenino',25,'superior','Ingeniería','UPTx','APIZACO','Inserción Laboral','2025-01-15',2025,'Vinculado'),
 ('P-00001-00002','PER-0002','PERSONA PRUEBA DOS','Masculino',30,'superior','Derecho','UATx','TLAXCALA','Prácticas Profesionales','2025-02-10',2025,'Vinculado'),
 ('A-00001-00003','PER-0001','PERSONA PRUEBA UNO','Femenino',25,'superior','Ingeniería','UPTx','APIZACO','Atención','2026-03-01',2026,'Vinculado');
insert into public.vacantes(id_vacante,id_registro_origen,fecha,empresa,sector_empresa,tipo_vacante,tipo_oportunidad,estado) values
 ('VAC-0001','ORI-0001','2026-01-10','EMPRESA PRUEBA SA','Manufactura','Soldador','Empleo','Activa'),
 ('VAC-0002','ORI-0002','2026-02-10','EMPRESA PRUEBA SA','Manufactura','Prácticas Profesionales','Prácticas Profesionales','Activa');
insert into public.vinculaciones(id_vinculacion,id_persona_maestro,id_registro_origen,nombre_persona,empresa,estatus,fecha_vinculacion) values
 ('VIN-20260101-1','PER-0001','I-00001-00001','PERSONA PRUEBA UNO','EMPRESA PRUEBA SA','Vinculado','2026-01-20');
