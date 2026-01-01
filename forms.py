from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, Email

class BookingForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[Email()])
    phone = StringField("Phone", validators=[DataRequired()])
    check_in = DateField("Check In", validators=[DataRequired()])
    check_out = DateField("Check Out", validators=[DataRequired()])
    submit = SubmitField("Confirm Booking")