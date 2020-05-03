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

'''
BASIC STRUCTURE
'''

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


'''
FEATURE 1: VIEW VISIBLE PHOTOS
POTENTIAL PROBLEM: DO WE SHOW PICS IN THE FRIENDGROUP?
'''
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


'''
FEATURE 3: POST A PHOTO
INTEGRATED WITHIN USER'S PROFILE PAGE
'''
@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    cursor = conn.cursor()
    query_pull = 'SELECT groupName, groupCreator FROM BelongTo WHERE username = %s OR groupCreator = %s'
    cursor.execute(query_pull, (user, user))
    fgs_data=cursor.fetchall()
    query = 'SELECT postingDate, pID, filePath FROM Photo WHERE poster = %s ORDER BY postingDate DESC'
    cursor.execute(query, (user))
    pics = cursor.fetchall()
    cursor.close()
    if(pics): disp_image(pics)
    return render_template('profile.html', username=user, fgs=fgs_data, posts=pics)


@app.route('/post', methods=['GET', 'POST'])
def post():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # check if the post request has the file part
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
        user = session['username']
        cursor = conn.cursor()
        photoBLOB = convertToBinaryData(photoPath)
        postingDate = datetime.datetime.today()
        allFollowers = check_followers(request.form['audiance']) #returns 1 if public, 0 if private
        caption = request.form['caption'] #caption is text
        query_push = 'INSERT INTO Photo (postingDate,filePath, allFollowers, caption, poster) VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(query_push, (postingDate, photoBLOB, allFollowers, caption, user))
        curr_pID = cursor.lastrowid
        print("Current pID: " + str(curr_pID))
        insert_group = request.form.getlist('selected_fg')
        print(insert_group)
        for item in insert_group:
            groupDet = item.split(" + ")
            query_fg_push = 'INSERT INTO SharedWith (pID, groupName, groupCreator) VALUES (%s, %s, %s)'
            cursor.execute(query_fg_push, (str(curr_pID), groupDet[0], groupDet[1]))
        conn.commit()
        cursor.close()
    return redirect(url_for('profile'))
        
    
'''
FEATURE 2: PHOTO DETAILS
SEPARATE PAGE AFTER CLICKING ON A PHOTO
'''
@app.route('/photoDetail', methods=['GET', 'POST'])
def photoDetail():
    if 'username' not in session:
        return redirect(url_for('login'))
    user=session['username']
    photo = request.args.get('pID')
    cursor = conn.cursor()
    error = None
    query_check = 'SELECT poster, allFollowers FROM Photo WHERE pID = %s'
    cursor.execute(query_check, (photo))
    data_check = cursor.fetchone() #dictcursor. fetchall returns list of dicts
    #PREVENT pID HIJACKING
    if(data_check['allFollowers'] == 1) or (data_check['poster'] == user):
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
    else:
        data1 = None
        data2 = None
        data3 = None
        error = "You do not have permission to view this photo."
    return render_template('photoDetail.html', photoDet=data1, tagged=data2, react=data3, error=error)


'''
FEATURE 5 & 11: MANAGE FRIEND GROUP
'''
@app.route('/friend_group',methods=['GET','POST'])
def friend_group():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    cursor = conn.cursor()
    query_c = 'SELECT * FROM FriendGroup WHERE groupCreator = %s'
    cursor.execute(query_c, (user))
    fgs_c_data = cursor.fetchall()
    query_i = 'SELECT groupName, groupCreator, description FROM BelongTo JOIN FriendGroup USING(groupName,groupCreator) WHERE username = %s'
    cursor.execute(query_i, (user))
    fgs_i_data = cursor.fetchall()
    query_pull = 'SELECT * FROM Follow WHERE followee = %s AND followStatus = 1' #SET AS 1 FOR NOW
    cursor.execute(query_pull, (user))
    followers_data = cursor.fetchall()
    cursor.close()
    return render_template('friend_group.html', fgscreated=fgs_c_data, fgsin=fgs_i_data, followers = followers_data, error=request.args.get('error'))


@app.route('/add_friend_group',methods=['GET','POST'])
def add_friend_group():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    group_name = request.form['group_name']
    description = request.form['description']
    cursor = conn.cursor()
    #dup check
    check = 'SELECT * FROM FriendGroup WHERE groupName = %s AND groupCreator = %s'
    cursor.execute(check,(group_name,user))
    data = cursor.fetchall()
    if(data):
        #If the previous query returns data, then user exists
        error = "This Friend Group already exists"
        return redirect(url_for('friend_group', error=error))
    query = 'INSERT INTO FriendGroup (groupName,groupCreator,description) VALUES(%s,%s,%s)'
    cursor.execute(query,(group_name,user,description))
    add_member = request.form.getlist('add_members_at_creation')
    print(add_member)
    for person in add_member:
        query_push = 'INSERT INTO BelongTo (username, groupName, groupCreator) VALUES (%s, %s, %s)'
        cursor.execute(query_push,(person, group_name, user))
    conn.commit()
    cursor.close()
    return redirect(url_for('friend_group'))
    

@app.route('/groupDetail/<creator>/<group>', methods=['GET', 'POST'])
def groupDetail(creator,group):
    if 'username' not in session:
        return redirect(url_for('login'))
    sess = False
    user = session['username']
    cursor = conn.cursor()
    query_member = 'SELECT * FROM BelongTo WHERE groupName = %s AND groupCreator = %s'
    cursor.execute(query_member, (group, creator))
    member_data = cursor.fetchall()
    if(user == creator):
        sess = True
    query_pics = 'SELECT * FROM SharedWith JOIN Photo USING (pID) WHERE groupName = %s AND groupCreator = %s'
    cursor.execute(query_pics, (group, creator))
    pics = cursor.fetchall()
    cursor.close()
    return render_template('groupDetail.html', group=request.args.get('group'), creator=request.args.get('creator'), error=request.args.get('error'), photos=pics, members = member_data, sess=sess, gn = group, gc = creator)
    
    
@app.route('/add_friend/<creator>/<group>', methods=['GET', 'POST'])
def add_friend(creator,group):
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    friend_name = request.form['friend_name']
    print(creator == user)
    error = None
    if(creator == user): #check if creator is managing friends
        cursor = conn.cursor()
        if(user == friend_name):
            error = "Cannot add group creator again. "
        else:
            checkuser = 'SELECT * FROM Person WHERE username = %s'
            cursor.execute(checkuser,friend_name)
            datau = cursor.fetchall()
            if not datau:
                error = "This user is not found. "
            else:
                #dup check
                checkmembership = 'SELECT * FROM BelongTo WHERE username = %s AND groupName = %s AND groupCreator = %s'
                cursor.execute(checkmembership,(friend_name,group,user))
                datam = cursor.fetchall()
                if(datam):
                    error = "This friend is already in your group. "
                else:
                    query = 'INSERT INTO BelongTo (groupName,groupCreator,username) VALUES(%s,%s,%s)'
                    cursor.execute(query,(group,user,friend_name))
                    conn.commit()
                    cursor.close()
    else:
        error = "Unable to add. "
    return redirect(url_for('groupDetail',group=group, creator=creator, error=error))

'''
FEATURE 4: MANAGE FOLLOWER
'''
@app.route('/manage_follow',methods=['GET'])
def manage_follow():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    query = 'SELECT * FROM Follow WHERE followee=%s AND followstatus=1'
    cursor = conn.cursor()
    cursor.execute(query, user)
    follower = cursor.fetchall()
    
    query = 'SELECT * FROM Follow WHERE follower=%s AND followstatus=1'
    cursor = conn.cursor()
    cursor.execute(query, user)
    followee = cursor.fetchall()
    
    query = 'SELECT * FROM Follow WHERE followee=%s AND followstatus=0'
    cursor = conn.cursor()
    cursor.execute(query, user)
    request = cursor.fetchall()
    
    return render_template('manage_follow.html', followers=follower, followees=followee, follow_requests=request)

@app.route('/add_follow',methods=['POST'])
def add_follow():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    follow_name = request.form['username']
    follow_status = 0
    query = 'INSERT INTO Follow(follower,followee,followStatus) VALUES (%s,%s,%s)'
    cursor = conn.cursor()
    cursor.execute(query,(follow_name,user,follow_status))
    conn.commit()
    cursor.close()
    return redirect(url_for('manage_follow'))

@app.route('/accept_follow/<follower>',methods=['POST'])
def accept_follow(follower):
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    query = 'UPDATE Follow SET followStatus = 1 WHERE follower = %s AND followee = %s'
    cursor = conn.cursor()
    cursor.execute(query,(follower,user))
    conn.commit()
    cursor.close()
    return redirect(url_for('manage_follow'))
    
@app.route('/decline_follow/<follower>',methods=['POST'])
def decline_follow(follower):
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    query = 'DELETE FROM Follow WHERE follower = %s AND followee = %s'
    cursor = conn.cursor()
    cursor.execute(query,(follower,user))
    conn.commit()
    cursor.close()
    return redirect(url_for('manage_follow'))


'''
FEATURE 10: SEARCH BY POSTER
'''

@app.route('/select_blogger', methods=['GET', 'POST'])
def select_blogger():
    #check that user is logged in
    #username = session['username']
    #should throw exception if username not found
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('select_blogger.html')
    
    
@app.route('/search_blogger', methods=['GET', 'POST'])
def search_blogger():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = session['username']
    name_input = request.form['username']
    cursor = conn.cursor()
    searchRes = name_input + '%'
    print(searchRes)
    query = 'SELECT DISTINCT username FROM Person WHERE username LIKE (%s)'
    cursor.execute(query,searchRes)
    data = cursor.fetchall()
    conn.commit()
    cursor.close()
    return render_template('select_blogger.html', user_list=data)



@app.route('/show_posts/<poster>', methods=['GET', 'POST'])
def show_posts(poster):
    user = session['username']
    cursor = conn.cursor()
    '''
    cleanup = 'DROP VIEW visiblePhoto'
    view = 'CREATE VIEW visiblePhoto AS (SELECT pID, poster,postingDate FROM Photo WHERE pID IN (SELECT pID FROM SharedWith WHERE groupName IN (SELECT groupName FROM BelongTo WHERE username = %s OR groupCreator = %s)) ORDER BY postingDate DESC)'
    query = 'SELECT * FROM visiblePhoto WHERE poster=%s'
    cursor.execute(view,(user,user))
    cursor.execute(query, poster)
    '''
    query='SELECT * FROM Photo JOIN Person ON (poster=username) WHERE pID IN (SELECT pID FROM Photo AS p JOIN Follow ON (poster = followee) WHERE follower = %s AND followStatus = 1 AND (allFollowers = 1 OR %s IN (SELECT username FROM BelongTo JOIN SharedWith USING (groupName, groupCreator) WHERE pID = p.pID))) ORDER BY postingDate DESC'
    cursor.execute(query,(poster,user))
    data = cursor.fetchall()
    #cursor.execute(cleanup)
    cursor.close()
    return render_template('show_posts.html', posts=data, poster_name = poster)

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
