#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect
import pymysql.cursors
import hashlib
import datetime
import os

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

#Initialize the app from Flask
app = Flask(__name__)


#Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 8889,
                       user='root',
                       password='root',
                       db='Finstagram',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Define a route to hello function
@app.route('/')
def hello():
    return render_template('index.html')

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    username = request.form['username']
    password = getHashed(request.form['password'])
    
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password']
    fName = request.form['firstName']
    lName = request.form['lastName']
    email = request.form['email']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = "This user already exists"
        return render_template('register.html', error = error)
    else:
        pHash = getHashed(password)
        ins = 'INSERT INTO Person VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(ins, (username, pHash, fName, lName, email))
        conn.commit()
        cursor.close()
        return render_template('index.html')


@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    cursor = conn.cursor()
    query = 'SELECT postingDate, pID, filePath FROM Photo WHERE (poster = %s OR allFollowers = %s) ORDER BY postingDate DESC'
    cursor.execute(query, (user, 1))
    data = cursor.fetchall()
    cursor.close()
    if(data): disp_image(data)
    return render_template('home.html', username=user, posts=data)

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    cursor = conn.cursor()
    query = 'SELECT postingDate, pID, filePath FROM Photo WHERE poster = %s ORDER BY postingDate DESC'
    cursor.execute(query, (user))
    data = cursor.fetchall()
    cursor.close()
    if(data): disp_image(data)
    return render_template('profile.html', username=user, posts=data)
    
@app.route('/photoDetail', methods=['GET', 'POST'])
def photoDetail():
    if 'username' not in session:
        return redirect(url_for('login'))
    photo = request.args.get('pID')
    cursor = conn.cursor()
    query1 = 'SELECT * FROM Photo JOIN Person ON (username = poster) WHERE pID = %s'
    cursor.execute(query1, (photo))
    data1 = cursor.fetchall()
    if(data1): disp_image(data1)
    query2 = 'SELECT * FROM Tag JOIN Person USING (username) WHERE (pID = %s AND tagStatus = 1)'
    cursor.execute(query2, (photo))
    data2 = cursor.fetchall()
    query3 = 'SELECT * FROM ReactTo WHERE pID = %s ORDER BY reactionTime DESC'
    cursor.execute(query3, (photo))
    data3 = cursor.fetchall()
    cursor.close()
    return render_template('photoDetail.html', photoDet=data1, tagged=data2, react=data3)
        
@app.route('/post', methods=['GET', 'POST'])
def post():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # check if the post request has the file part
        print(request.files)
        if 'photo' not in request.files:
            print('No file part')
            return redirect(url_for('home'))
        photoPath = request.files['photo']
        # if user does not select file, browser also
        # submit an empty part without filename
        if photoPath.filename == '':
            print('No selected file')
            return redirect(url_for('home'))
        if photoPath and not allowed_file(photoPath.filename):
            print('File type not allowed')
            return redirect(url_for('home'))
        username = session['username']
        cursor = conn.cursor()
        photoBLOB = convertToBinaryData(photoPath)
        postingDate = datetime.datetime.today()
        allFollowers = check_followers(request.form['audiance']) #returns 1 if public, 0 if private
        caption = request.form['caption'] #caption is text
        query = 'INSERT INTO Photo (postingDate,filePath, allFollowers, caption, poster) VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(query, (postingDate, photoBLOB, allFollowers, caption, username))
        conn.commit()
        cursor.close()
    return redirect(url_for('profile'))

@app.route('/select_blogger')
def select_blogger():
    #check that user is logged in
    #username = session['username']
    #should throw exception if username not found
    
    cursor = conn.cursor()
    query = 'SELECT DISTINCT username FROM blog'
    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()
    return render_template('select_blogger.html', user_list=data)

@app.route('/show_posts', methods=["GET", "POST"])
def show_posts():
    poster = request.args['poster']
    cursor = conn.cursor();
    query = 'SELECT ts, blog_post FROM blog WHERE username = %s ORDER BY ts DESC'
    cursor.execute(query, poster)
    data = cursor.fetchall()
    cursor.close()
    return render_template('show_posts.html', poster_name=poster, posts=data)

@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')


''' Supplements used for Flask implementation '''
def getHashed(password): 
    salt = "Finstagram"
    saltedPswd = password + salt
    pHash = hashlib.sha256(saltedPswd.encode()).hexdigest()
    return pHash

### BLOB related implementations ###
def convertToBinaryData(file):
    # Convert digital data to binary format
    binaryData = file.read()
    return binaryData

def disp_image(data):
    folderPath = './static/user_uploads/'
    if not os.path.exists(folderPath):
        os.makedirs(folderPath)
    for item in data:
        image = item['filePath']
        filePath = folderPath + str(item['pID'])
        write_file(image, filePath)
    files = []
    with os.scandir(folderPath) as directory:
        for item in directory:
            if item.name[0] != '.':
                files.append(folderPath + '/' + str(item.name))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_followers(item):
    if(item == 0 or item == 1):
        return item
    return 0

def write_file(data, filename):
    # Convert binary data to proper format and write it on Hard Disk
    with open(filename, 'wb') as file:
        file.write(data)

app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug = True)
