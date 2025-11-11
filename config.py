# config.py
import streamlit_authenticator as stauth

# 1. Definimos las contraseñas claras en una lista
PASSWORDS_CLARAS = ['administradorFantasy25', '1234', '2121']

# 2. Creamos una lista hasheada manualmente.
#    Usamos una comprensión de lista para llamar a .hash() para CADA contraseña.
#    Esto evita el bug de la librería con las listas.
HASED_PASSWORDS = [stauth.Hasher().hash(password) for password in PASSWORDS_CLARAS]

USER_CONFIG = {
    'credentials': {
        'usernames': {
            'admin_user': {
                'email': 'admin@fantasy.com',
                'name': 'Administrador',
                'password': HASED_PASSWORDS[0],
                'role': 'Admin',
                'allowed_leagues': []
            },
            'user00': {
                'email': 'usuarioAKC@fantasy.com',
                'name': 'Usuario Liga AKC',
                'password': HASED_PASSWORDS[1],
                'role': 'User',
                'allowed_leagues': ['Liga AKC 2025-26']
            },
            'user01': {
                'email': 'usuarioPrueba@fantasy.com',
                'name': 'Usuario Prueba',
                'password': HASED_PASSWORDS[2],
                'role': 'User',
                'allowed_leagues': []
            }
        }
    },
    'cookie': {
        'expiry_days': 30,
        'key': 'aplicacion_para_analisis_fantasy_lebp', # ¡Cambia esto!
        'name': 'fantasy_auth_cookie'
    }
}