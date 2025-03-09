# Configuración de Masscer

Una vez seguiste todos los pasos de instalación ([Instalación de Herramientas Esenciales](./installations.md)), puedes configurar la aplicación para agregar credenciales de la base de datos, instalar las dependencias y ejecutar la aplicación.

## Clonar el proyecto

1. Crear una carpeta en el desktop.
2. Arrastrar la carpeta hacia el ícono de VSCode.
3. Abrir una terminal de Bash en VSCode.

> Puedes usar la combinación de teclas **Ctrl + `** para abrir la terminal. (La tecla backtick se encuentra debajo de la tecla **Esc**)

4. Clonar el repositorio

```bash
git clone https://github.com/Masscer-AI/Project.git .
```

5. Instalar las dependencias

```bash
./install.sh
```

6. Instalar contenedores
   > Esto creará un contenedor de PostgreSQL que es una base de datos relacional usada por Masscer para almacenar la información de los usuarios, agentes, conversaciones, etc.

```bash
./createPostgres.sh -u USUARIO -p CONTRASEÑA -d NOMBREDELABASE
```

Este comando va a retornar una cadena de conexión a la base de datos. DB_CONNECTION_STRING= que tiene la forma:

```bash
postgres://USUARIO:CONTRASEÑA@localhost:5432/NOMBREDELABASE
```

7. Copiar el archivo `.env.example` a `.env`

```bash
cp .env.example .env
```

8. Editar el archivo `.env` como mínimo con las credenciales de la base de datos y la OPENAI_API_KEY

```bash
DB_CONNECTION_STRING=postgres://USUARIO:CONTRASEÑA@localhost:5432/NOMBREDELABASE
OPENAI_API_KEY=sk-your-openai-key
```

> Para agregar más credenciales, simplemente se reemplaza el valor de la variable en el archivo `.env` con el valor que se desea agregar. Asegúrate que se esté guardando el archivo `.env`, si estás en VSCode, puedes usar la combinación de teclas **Ctrl + S** para guardar el archivo.

9. Ejecutar la aplicación, contenedores, base de datos vectorial, construir el frontend.

```bash
./init.sh
```

10. Ejecutar los workers en segundo plano

```bash
./runWorkers.sh
```




