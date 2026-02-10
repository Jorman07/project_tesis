from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.services.auth_service import authenticate, register_user


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# =========================
# LOGIN
# =========================

@auth_bp.route('/login', methods=['GET'])
def login_view():
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    cedula = data.get('cedula')
    password = data.get('password')

    if not cedula or not password:
        return jsonify({'message': 'Datos incompletos'}), 400

    user, err = authenticate(cedula, password)

    if err:
        return jsonify({'message': err}), 401


    # Guardar sesión completa
    session['user'] = {
        "id": user["id_usuario"],
        "id_usuario": user["id_usuario"],
        "cedula": user["cedula"],
        "nombre": f"{user['nombres']} {user['apellidos']}",
        "rol": user["rol"]
    }


    return jsonify({'redirect': '/'})


# =========================
# REGISTRO
# =========================

@auth_bp.route("/register", methods=["GET", "POST"])
def register_view():
    next_url = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        nombres = request.form.get("nombres")
        apellidos = request.form.get("apellidos")
        cedula = request.form.get("cedula")
        password = request.form.get("password")
        rol = request.form.get("rol")

        if not all([nombres, apellidos, cedula, password, rol]):
            return render_template("register.html", error="Todos los campos son obligatorios", next=next_url)

        # Seguridad: no permitir registrar ADMINISTRADOR desde formulario público
        if rol == "ADMINISTRADOR":
            return render_template("register.html", error="No está permitido registrarse como ADMINISTRADOR.", next=next_url)

        result = register_user(cedula, nombres, apellidos, password, rol)

        if isinstance(result, dict) and result.get("error"):
            return render_template("register.html", error=result["error"], next=next_url)

        # Si viene next, regresa ahí; si no, manda al login
        if next_url:
            return redirect(next_url)

        return redirect(url_for("auth.login_view"))

    return render_template("register.html", next=next_url)


# =========================
# LOGOUT
# =========================

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login_view'))
