from flask import Flask, render_template, url_for

bryl = Flask(__name__)

@bryl.route("/")
def home():
    return render_template("index.html")

@bryl.route("/about")
def about():
    return render_template("about.html")

@bryl.route("/contact")
def contact():
    return render_template("contact.html")

@bryl.route("/register")
def register():
    return render_template("register.html")

@bryl.route("/forgot_password")
def forgot_password():
    return render_template("forgot_password.html")

@bryl.route("/logout")
def logout():
    return "You have been logged out."

if __name__ == "__main__":
    bryl.run(debug=True)
