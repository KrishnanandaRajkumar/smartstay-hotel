from flask import Flask, render_template, request, redirect, session, url_for
from models import get_db
from config import SECRET_KEY
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash

app = Flask(__name__)
app.secret_key = SECRET_KEY

print("Admin cancel route loaded")
# -------------------------
# HOTEL FRONT PAGE
# -------------------------
@app.route("/")
def home():
    return render_template("home.html")

# -------------------------
# ROOMS PAGE (WITH AVAILABILITY FILTER)
# -------------------------
@app.route("/rooms")
def rooms():
    check_in = request.args.get("check_in")
    check_out = request.args.get("check_out")

    db = get_db()
    cur = db.cursor()

    if check_in and check_out:
        # 🔴 Show only available rooms
        cur.execute("""
            SELECT *
            FROM room r
            WHERE NOT EXISTS (
                SELECT 1 FROM booking b
                WHERE b.room_id = r.id
                AND b.status != 'CANCELLED'
                AND %s < b.check_out
                AND %s > b.check_in
            )
        """, (check_in, check_out))
    else:
        # Default: show all rooms
        cur.execute("SELECT * FROM room")

    rooms = cur.fetchall()
    db.close()

    return render_template(
        "index.html",
        rooms=rooms,
        check_in=check_in,
        check_out=check_out
    )

# -------------------------
# FOOD MENU PAGE
# -------------------------
@app.route("/food-menu")
def food_menu():
    return render_template("food_menu.html")

# -------------------------
# CUSTOMER REGISTER
# -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = generate_password_hash(request.form.get("password"))

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                "INSERT INTO customer (name, email, password) VALUES (%s,%s,%s)",
                (name, email, password)
            )
            db.commit()
        except:
            db.close()
            return "Email already registered"
        db.close()
        return redirect(url_for("login"))

    return render_template("register.html")


# -------------------------
# CUSTOMER LOGIN
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id, password FROM customer WHERE email=%s",
            (email,)
        )
        user = cur.fetchone()
        db.close()

        if user and check_password_hash(user[1], password):
            session["customer_id"] = user[0]
            return redirect(url_for("my_bookings"))

        return "Invalid login credentials"

    return render_template("login.html")


# -------------------------
# CUSTOMER LOGOUT
# -------------------------
@app.route("/logout")
def logout():
    session.pop("customer_id", None)
    return redirect(url_for("home"))


# -------------------------
# BOOK ROOM
# -------------------------
@app.route("/book/<int:room_id>", methods=["GET", "POST"])
def book(room_id):
    if request.method == "POST":

        # -------------------------
        # Guest Details
        # -------------------------
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")

        # -------------------------
        # Stay Details
        # -------------------------
        check_in = request.form.get("check_in")
        check_out = request.form.get("check_out")
        check_in_time = request.form.get("check_in_time")
        check_out_time = request.form.get("check_out_time")
        guests = int(request.form.get("guests"))

        # -------------------------
        # Services
        # -------------------------
        food_option = request.form.get("food_option")
        gym = True if request.form.get("gym") else False
        pool = True if request.form.get("pool") else False

        db = get_db()
        cur = db.cursor()

        # -------------------------
        # Room Info
        # -------------------------
        cur.execute(
            "SELECT price, max_guests FROM room WHERE id=%s",
            (room_id,)
        )
        room_price, max_guests = cur.fetchone()

        if guests > max_guests:
            db.close()
            return render_template(
                "booking.html",
                error="Number of guests exceeds room capacity."
            )

        # -------------------------
        # Date Validation
        # -------------------------
        nights = (
            datetime.strptime(check_out, "%Y-%m-%d")
            - datetime.strptime(check_in, "%Y-%m-%d")
        ).days

        if nights <= 0:
            db.close()
            return render_template(
                "booking.html",
                error="Check-out date must be after check-in."
            )

        # -------------------------
        # 🔴 HARD SAFETY CHECK (Double Booking Prevention)
        # -------------------------
        cur.execute("""
            SELECT 1
            FROM booking
            WHERE room_id = %s
              AND status != 'CANCELLED'
              AND %s < check_out
              AND %s > check_in
        """, (room_id, check_in, check_out))

        if cur.fetchone():
            db.close()
            return render_template(
                "booking_unavailable.html",
                message="Sorry, this room is not available for the selected dates. Please choose another room or date."
            )

        # -------------------------
        # Price Calculation
        # -------------------------
        total_price = nights * room_price

        if food_option == "Breakfast":
            total_price += 300
        elif food_option == "Full Board":
            total_price += 900

        if gym:
            total_price += 500
        if pool:
            total_price += 300

        # -------------------------
        # Insert Guest
        # -------------------------
        cur.execute(
            "INSERT INTO guest (name, email, phone) VALUES (%s,%s,%s) RETURNING id",
            (name, email, phone)
        )
        guest_id = cur.fetchone()[0]

        # -------------------------
        # Insert Booking (CONFIRMED)
        # -------------------------
        cur.execute("""
            INSERT INTO booking
            (guest_id, room_id, check_in, check_out,
             check_in_time, check_out_time,
             guests, food_option, gym, pool,
             total_price, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'CONFIRMED')
            RETURNING id
        """, (
            guest_id, room_id,
            check_in, check_out,
            check_in_time, check_out_time,
            guests, food_option, gym, pool,
            total_price
        ))

        booking_id = cur.fetchone()[0]

        db.commit()
        db.close()

        # 🔴 Redirect to Booking Summary (KEY FIX)
        return redirect(url_for("booking_summary", booking_id=booking_id))

    return render_template("booking.html")
# -------------------------
# BOOKING SUCCESS
# -------------------------
@app.route("/success")
def success():
    return render_template("success.html")

# -------------------------
# CUSTOMER BOOKINGS
# -------------------------
@app.route("/my-bookings")
def my_bookings():
    if not session.get("customer_id"):
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT r.room_number,
               b.check_in,
               b.check_out,
               b.guests,
               b.total_price,
               b.status,
               b.id
        FROM booking b
        JOIN room r ON b.room_id = r.id
        JOIN guest g ON b.guest_id = g.id
        WHERE g.email = (
            SELECT email FROM customer WHERE id=%s
        )
        ORDER BY b.created_at DESC
    """, (session["customer_id"],))

    bookings = cur.fetchall()
    db.close()

    # 🔴 Detect admin-cancelled bookings
    has_cancelled = any(b[5] == "CANCELLED" for b in bookings)

    return render_template(
        "my_bookings.html",
        bookings=bookings,
        has_cancelled=has_cancelled
    )
# -------------------------
# CANCEL BOOKING (CUSTOMER)
# -------------------------
@app.route("/cancel-booking/<int:booking_id>")
def cancel_booking(booking_id):
    if not session.get("customer_id"):
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()

    # Ensure booking belongs to logged-in customer
    cur.execute("""
        UPDATE booking
        SET status = 'CANCELLED'
        WHERE id = %s AND guest_id IN (
            SELECT g.id FROM guest g
            JOIN customer c ON g.email = c.email
            WHERE c.id = %s
        )
    """, (booking_id, session["customer_id"]))

    db.commit()
    db.close()

    return redirect(url_for("my_bookings"))

# -------------------------
# EDIT BOOKING (CUSTOMER)
# -------------------------
@app.route("/edit-booking/<int:booking_id>", methods=["GET", "POST"])
def edit_booking(booking_id):
    if not session.get("customer_id"):
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        check_in = request.form.get("check_in")
        check_out = request.form.get("check_out")
        food_option = request.form.get("food_option")
        gym = True if request.form.get("gym") else False
        pool = True if request.form.get("pool") else False

        # Get room price
        cur.execute("""
            SELECT r.price
            FROM booking b
            JOIN room r ON b.room_id = r.id
            WHERE b.id = %s
        """, (booking_id,))
        price = cur.fetchone()[0]

        nights = (
            datetime.strptime(check_out, "%Y-%m-%d")
            - datetime.strptime(check_in, "%Y-%m-%d")
        ).days

        total_price = nights * price

        if food_option == "Breakfast":
            total_price += 300
        elif food_option == "Full Board":
            total_price += 900
        if gym:
            total_price += 500
        if pool:
            total_price += 300

        cur.execute("""
            UPDATE booking
            SET check_in=%s,
                check_out=%s,
                food_option=%s,
                gym=%s,
                pool=%s,
                total_price=%s
            WHERE id=%s
        """, (
            check_in, check_out,
            food_option, gym, pool,
            total_price, booking_id
        ))

        db.commit()
        db.close()
        return redirect(url_for("my_bookings"))

    # GET: Load existing booking
    cur.execute("""
        SELECT check_in, check_out, food_option, gym, pool
        FROM booking
        WHERE id=%s
    """, (booking_id,))
    booking = cur.fetchone()
    db.close()

    return render_template("edit_booking.html", booking=booking, booking_id=booking_id)

# -------------------------
# BOOKING SUMMARY
# -------------------------
@app.route("/summary/<int:booking_id>")
def booking_summary(booking_id):
    if not session.get("customer_id"):
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT
            r.room_number,
            b.check_in,
            b.check_out,
            b.guests,
            b.food_option,
            b.gym,
            b.pool,
            b.total_price
        FROM booking b
        JOIN room r ON b.room_id = r.id
        WHERE b.id = %s
          AND b.status = 'CONFIRMED'
    """, (booking_id,))

    booking = cur.fetchone()
    db.close()

    if not booking:
        return redirect(url_for("my_bookings"))

    return render_template(
        "booking_summary.html",
        booking_id=booking_id,
        booking=booking
    )

# -------------------------
# PAYMENT (CARD / UPI SIMULATION)
# -------------------------
@app.route("/pay/<int:booking_id>", methods=["GET", "POST"])
def pay_now(booking_id):
    if not session.get("customer_id"):
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()

    # Fetch booking (NO email re-check here)
    cur.execute("""
        SELECT r.room_number, b.total_price, b.status
        FROM booking b
        JOIN room r ON b.room_id = r.id
        WHERE b.id = %s
          AND b.status = 'CONFIRMED'
    """, (booking_id,))

    booking = cur.fetchone()

    if not booking:
        db.close()
        return redirect(url_for("my_bookings"))

    # POST = simulate payment
    if request.method == "POST":
        cur.execute(
            "UPDATE booking SET status='PAID' WHERE id=%s",
            (booking_id,)
        )
        db.commit()
        db.close()
        return redirect(url_for("invoice", booking_id=booking_id))

    db.close()

    # GET = show payment page
    return render_template(
        "payment.html",
        booking_id=booking_id,
        room=booking[0],
        amount=booking[1]
    )

# -------------------------
# INVOICE / RECEIPT
# -------------------------
@app.route("/invoice/<int:booking_id>")
def invoice(booking_id):
    if not session.get("customer_id"):
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT
            r.room_number,
            b.check_in,
            b.check_out,
            b.guests,
            b.food_option,
            b.gym,
            b.pool,
            b.total_price,
            b.status,
            b.id
        FROM booking b
        JOIN room r ON b.room_id = r.id
        JOIN guest g ON b.guest_id = g.id
        WHERE b.id = %s
          AND b.status = 'PAID'
          AND g.email = (
              SELECT email FROM customer WHERE id = %s
          )
    """, (booking_id, session["customer_id"]))

    booking = cur.fetchone()
    db.close()

    if not booking:
        return redirect(url_for("my_bookings"))

    return render_template(
        "invoice.html",
        booking=booking
    )

# -------------------------
# ADMIN LOGIN
# -------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == "admin" and request.form.get("password") == "admin123":
            session["admin"] = True
            return redirect(url_for("admin_bookings"))
    return render_template("admin_login.html")

# -------------------------
# ADMIN DASHBOARD
# -------------------------
@app.route("/admin/bookings")
def admin_bookings():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    db = get_db()
    cur = db.cursor()

    # 🔴 UPDATED QUERY (includes status + booking id)
    cur.execute("""
        SELECT
            g.name,          -- b[0]
            r.room_number,   -- b[1]
            b.check_in,      -- b[2]
            b.check_out,     -- b[3]
            b.guests,        -- b[4]
            b.food_option,   -- b[5]
            b.gym,           -- b[6]
            b.pool,          -- b[7]
            b.total_price,   -- b[8]
            b.status,        -- b[9]
            b.id             -- b[10]
        FROM booking b
        JOIN guest g ON b.guest_id = g.id
        JOIN room r ON b.room_id = r.id
        ORDER BY b.created_at DESC
    """)

    bookings = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM booking")
    total_bookings = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM booking WHERE check_in = CURRENT_DATE")
    today_checkins = cur.fetchone()[0]

    db.close()

    return render_template(
        "admin_bookings.html",
        bookings=bookings,
        total=total_bookings,
        today=today_checkins
    )

# -------------------------
# ADMIN LOGOUT
# -------------------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

# -------------------------
# ADMIN CANCEL BOOKING
# -------------------------
@app.route("/admin/cancel-booking/<int:booking_id>")
def admin_cancel_booking(booking_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    db = get_db()
    cur = db.cursor()

    # Get guest email (for customer notification)
    cur.execute("""
        SELECT g.email
        FROM booking b
        JOIN guest g ON b.guest_id = g.id
        WHERE b.id = %s
    """, (booking_id,))
    guest_email = cur.fetchone()

    # Cancel booking
    cur.execute("""
        UPDATE booking
        SET status = 'CANCELLED'
        WHERE id = %s
    """, (booking_id,))

    db.commit()
    db.close()

    # Store message for customer
    if guest_email:
        session["cancel_notice"] = (
            "Your booking has been cancelled by the hotel administration."
        )

    return redirect(url_for("admin_bookings"))

if __name__ == "__main__":
    app.run()