import os
from flask import Flask, render_template, request, url_for, redirect, session
from functools import wraps
from database import get_connection
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            return "<h1>Access Denied ❌</h1>", 403

        return f(*args, **kwargs)

    return decorated_function

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM users WHERE username = %s AND password = %s"

        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]

            return redirect(url_for("dashboard"))
        else:
            return "<h1>Invalid Username or Password ❌</h1>"
        
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        phone_number = request.form["phone_number"]

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        check_query = """
        SELECT * FROM users
        WHERE email = %s
        """

        cursor.execute(check_query, (email,))

        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            conn.close()
            return "<h2>Email already exists. Please use another email.</h2>"

        query = """
        INSERT INTO users (username, email, password, phone_number)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(query, (username, email, password, phone_number))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



@app.route("/menu")
def menu():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM food_items")

    food_items = cursor.fetchall()

    cart_count = 0

    if "user" in session:

        cursor.execute(
            """
            SELECT COALESCE(SUM(cart.quantity), 0) AS cart_count
            FROM cart
            JOIN users
                ON cart.user_id = users.user_id
            WHERE users.username = %s
            """,
            (session["user"],)
        )

        result = cursor.fetchone()

        cart_count = result["cart_count"]


    cursor.close()
    conn.close()

    return render_template(
        "menu.html",
        food_items=food_items,
        cart_count=cart_count
    )


@app.route("/admin")
@admin_required
def admin():

    return render_template("admin.html")


@app.route("/add-food", methods=["GET", "POST"])
@admin_required
def add_food_item():

    if request.method == "POST":

        food_name = request.form["food_name"]
        category = request.form["category"]
        price = request.form["price"]
        description = request.form["description"]

        conn = get_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO food_items (food_name, category, price, description)
        VALUES (%s, %s, %s, %s)
        """

        cursor.execute(query, (food_name, category, price, description))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("menu"))
    
    return render_template("add_food.html")

@app.route("/manage-food")
@admin_required
def manage_food():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM food_items")
    foods = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("manage_food.html", foods=foods)


@app.route("/edit-food/<int:food_id>", methods=["GET", "POST"])
@admin_required
def edit_food(food_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":

        food_name = request.form["food_name"]
        category = request.form["category"]
        price = request.form["price"]
        description = request.form["description"]

        query = """
        UPDATE food_items
        SET food_name=%s,
            category=%s,
            price=%s,
            description=%s
        WHERE food_id=%s
        """

        cursor.execute(
            query,
            (food_name, category, price, description, food_id)
        )

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("manage_food"))

    cursor.execute(
        "SELECT * FROM food_items WHERE food_id=%s",
        (food_id,)
    )

    food = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("edit_food.html", food=food)

@app.route("/delete-food/<int:food_id>")
@admin_required
def delete_food(food_id):

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    DELETE FROM food_items
    WHERE food_id = %s
    """

    cursor.execute(query, (food_id,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("manage_food"))

@app.route("/add-to-cart/<int:food_id>")
def add_to_cart(food_id):

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT user_id FROM users WHERE username=%s",
        (session["user"],)
    )

    user = cursor.fetchone()

    query = """
    INSERT INTO cart (user_id, food_id, quantity)
    VALUES (%s, %s, %s)
    """

    cursor.execute(query, (user["user_id"], food_id, 1))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("menu"))

@app.route("/cart")
def cart():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        cart.cart_id,
        food_items.food_name,
        food_items.price,
        cart.quantity
    FROM cart

    JOIN users
        ON cart.user_id = users.user_id

    JOIN food_items
        ON cart.food_id = food_items.food_id

    WHERE users.username = %s
    """

    cursor.execute(query, (session["user"],))

    cart_items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("cart.html", cart_items=cart_items)


@app.route("/place-order", methods=["GET", "POST"])
def place_order():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT user_id FROM users WHERE username = %s",
        (session["user"],)
    )

    user = cursor.fetchone()

    query = """
    SELECT cart.food_id, cart.quantity, food_items.price
    FROM cart
    JOIN food_items
        ON cart.food_id = food_items.food_id
    WHERE cart.user_id = %s
    """

    cursor.execute(query, (user["user_id"],))

    cart_items = cursor.fetchall()

    if not cart_items:

        cursor.close()
        conn.close()

        return "<h2>Your cart is empty! 🛒</h2>"

    total = 0

    for item in cart_items:

        total += float(item["price"]) * item["quantity"]


    if request.method == "GET":

        cursor.close()
        conn.close()

        return render_template(
            "payment.html",
            total=total
        )


    payment_method = request.form["payment_method"]


    order_query = """
    INSERT INTO orders (user_id, total)
    VALUES (%s, %s)
    """

    cursor.execute(
        order_query,
        (user["user_id"], total)
    )

    order_id = cursor.lastrowid


    item_query = """
    INSERT INTO order_items (order_id, food_id, quantity)
    VALUES (%s, %s, %s)
    """

    for item in cart_items:

        cursor.execute(
            item_query,
            (
                order_id,
                item["food_id"],
                item["quantity"]
            )
        )


    cursor.execute(
        "DELETE FROM cart WHERE user_id = %s",
        (user["user_id"],)
    )


    conn.commit()

    cursor.close()
    conn.close()

    return render_template(
        "order_success.html",
        order_id=order_id,
        total=total,
        payment_method=payment_method
    )


@app.route("/orders")
def orders():

    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT orders.order_id,
           orders.total,
           orders.status,
           orders.order_date
    FROM orders
    JOIN users
        ON orders.user_id = users.user_id
    WHERE users.username = %s
    ORDER BY orders.order_date DESC
    """

    cursor.execute(query, (session["user"],))

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("orders.html", orders=orders)

@app.route("/admin/orders")
@admin_required
def admin_orders():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT
        orders.order_id,
        users.username,
        orders.total,
        orders.status,
        orders.order_date
    FROM orders
    JOIN users
        ON orders.user_id = users.user_id
    ORDER BY orders.order_date DESC
    """

    cursor.execute(query)

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/update-order/<int:order_id>", methods=["GET", "POST"])
@admin_required
def update_order(order_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":

        status = request.form["status"]

        query = """
        UPDATE orders
        SET status = %s
        WHERE order_id = %s
        """

        cursor.execute(query, (status, order_id))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("admin_orders"))

    cursor.execute(
        "SELECT * FROM orders WHERE order_id = %s",
        (order_id,)
    )

    order = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("update_order.html", order=order)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)