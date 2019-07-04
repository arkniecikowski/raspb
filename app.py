#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
import jwt
from PIL import Image
import git
import json
import zipfile
import shutil
from datetime import datetime
import datetime
import os
import pytz
from os.path import basename
import base64
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

pathStore = 'media/pi/183B-F811/magazyn'
os.makedirs(os.path.abspath(os.path.join(os.sep, pathStore)), exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pass321'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///berry.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
CORS(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.Integer, unique=True)
    name = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    admin = db.Column(db.Boolean)
    avatar = db.Column(db.LargeBinary)

class Files(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.Integer)
    uid = db.Column(db.Integer, unique=True)
    wai = db.Column(db.Text)
    commit_id = db.Column(db.Integer, default=None)
    message = db.Column(db.Text, default=None)
    name = db.Column(db.String(100))
    data = db.Column(db.DateTime, default=datetime.datetime.now(pytz.timezone('Europe/Warsaw')))
    isFolder = db.Column(db.Boolean)
    fileExtension = db.Column(db.String(50))

class Versions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.Integer)
    uid = db.Column(db.Integer, unique=True)
    file_uid = db.Column(db.Integer)
    commit_id = db.Column(db.Integer, default=None)
    message = db.Column(db.Text)
    wai = db.Column(db.Text)
    data = db.Column(db.DateTime, default=db.func.current_timestamp())
    fileExtension = db.Column(db.String(50))

out = []

class Shared(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, unique=True)
    public_id = db.Column(db.Integer)
    share_uid = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.datetime.now(pytz.timezone('Europe/Warsaw')))
    fileExtension = db.Column(db.String(50))
    isFolder = db.Column(db.Boolean)



def odkoduj_publicID(token):
    return jwt.decode(token, app.config['SECRET_KEY'])

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        formData = request.form
        jsondata = request.get_json()

        try:
            if formData['xaccesstoken'] != '':
                token = formData['xaccesstoken']
        except:
            pass

        try:
            if jsondata['xaccesstoken'] != '':
                token = jsondata['xaccesstoken']
        except:
            pass

        if not token:
            return jsonify({'message': 'Token missing!!'}), 404
        try:
            data = odkoduj_publicID(token)
            current_user = User.query.filter_by(public_id=data['public_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 404

        return f(current_user, *args, **kwargs)
    return decorated

def jsonWAI(wai):
    j = json.loads(wai)
    r = ""
    for i in j:
        r += str(i['wai'])
    return r


@app.route('/api/add_file', methods=['POST'])
@token_required
def add_file(current_user):

    #Pobrany plik
    dataMyFile = request.files

    addFileGuard = True

    for i in range(len(dataMyFile)):
        addFileGuard = True
        f = 'file'+str(i)

        dataFile = dataMyFile[f]

        #Pobrane dane
        dataMeta = request.form

        #Path gdzie zapisać
        WAI = jsonWAI(dataMeta['wai'])

        #Typ
        typ = dataFile.content_type
        try:
            #PID - public_id
            PID = current_user.public_id

            files = Files.query.filter_by(public_id=PID).filter_by(wai=WAI).all()

            #Tworzenie ścieżki
            WP_ID = PID+WAI

            #Tworzenie UID
            UID = str(uuid.uuid4())
            newImageName = str(uuid.uuid4())
            #Secure filename
            filename = secure_filename(dataFile.filename)

            for file in files:
                if file.name == dataFile.filename:
                    addFileGuard = False,

            xs = (dataFile.filename).split('.')
            if xs[0] == 'image':
                addFileGuard = True
                filename = newImageName + '.' + xs[1]

            if addFileGuard:
                # Tworzenie folderu jeżeli nie istnieje
                os.makedirs(os.path.abspath(os.path.join(os.sep, pathStore, WP_ID)), exist_ok=True)

                # Dodanie pliku we wskazane miejsce
                dataFile.save(os.path.abspath(os.path.join(os.sep, pathStore, WP_ID, filename)))

                adata = datetime.datetime.now(pytz.timezone('Europe/Warsaw'))

                new_file = Files(public_id=PID,
                                 uid=UID,
                                 wai=WAI,
                                 # binaryCode=binary,
                                 data=adata,
                                 name=filename,
                                 isFolder=False,
                                 fileExtension=typ
                                 )
                db.session.add(new_file)
                db.session.commit()
        except:
            return jsonify({'msg': 'Błąd przy dodawaniu pliku!'})

    return jsonify({'msg': 'Plik dodany!'})



@app.route('/api/add_folder', methods=['POST'])
@token_required
def add_folder(current_user):

    dataMyFile = request.files

    # Pobrane dane
    dataMeta = request.form

    # Path gdzie zapisać
    WAI = jsonWAI(dataMeta['wai'])

    # PID - public_id
    PID = current_user.public_id

    # Tworzenie ścieżki
    WP_ID = PID + WAI
    try:
        for i in range(len(dataMyFile)):
            addFileGuard = True
            UID = '/'
            awai = WAI
            awp_id = WP_ID
            f = 'file'+str(i)
            dataFile = dataMyFile[f]
            dataPathSplit = dataFile.filename.split('/')

            for i in range(len(dataPathSplit)-1):

                addFileArrayGuard = True
                files = Files.query.filter_by(public_id=PID).filter_by(wai=awai).all()

                for file in files:
                    if file.name == dataPathSplit[i]:
                        addFileArrayGuard = False
                        UID = file.uid

                if addFileArrayGuard:
                    UID = str(uuid.uuid4())
                    os.makedirs(os.path.abspath(os.path.join(os.sep, pathStore, awp_id, UID)), exist_ok=True)
                    filename = secure_filename(dataPathSplit[i])

                    new_file = Files(public_id=PID,
                                     uid=UID,
                                     wai=awai,
                                     name=filename,
                                     isFolder=True,
                                     fileExtension=None
                                     )

                    db.session.add(new_file)
                db.session.commit()

                awp_id = awp_id + UID + '/'
                awai = awai + UID + '/'

            files = Files.query.filter_by(public_id=PID).filter_by(wai=awai).all()

            for file in files:
                if file.name == dataPathSplit[-1]:
                    addFileGuard = False

            if addFileGuard:
                dataFile.save(os.path.abspath(os.path.join(os.sep, pathStore, awp_id, dataPathSplit[-1])))
                UID = str(uuid.uuid4())
                filename = secure_filename(dataPathSplit[-1])
                new_file = Files(public_id=PID,
                                 uid=UID,
                                 wai=awai,
                                 name=filename,
                                 isFolder=False,
                                 fileExtension=dataFile.content_type
                                 )

                db.session.add(new_file)
                db.session.commit()
    except:
        return jsonify({'msg': 'Błąd z dodawanie plików!'})

    return jsonify({'msg': 'Folder z plikami dodany'})

@app.route('/api/make_folder', methods=['POST'])
@token_required
def make_folder(current_user):

    #Pobrane dane
    dataMeta = request.form

    #Nazwa folderu
    folderName = dataMeta['folder']

    #Path gdzie zapisać
    WAI = jsonWAI(dataMeta['wai'])

    #PID - public_id
    PID = current_user.public_id

    #Tworzenie ścieżki
    WP_ID = PID+WAI

    #Tworzenie UID
    UID = str(uuid.uuid4())

    fs = Files.query.filter_by(public_id=current_user.public_id).filter_by(wai=WAI).all()

    print(fs)
    for f in fs:
        if folderName == f.name:
            return jsonify({'msg':'Nazwa zajęta'})

    try:
        #Tworzenie folderu jeżeli nie istnieje
        os.makedirs(os.path.abspath(os.path.join(os.sep, pathStore, WP_ID, UID)), exist_ok=True)
        new_file = Files(public_id=PID,
                         uid=UID,
                         wai=WAI,
                         # binaryCode=None,
                         name=folderName,
                         isFolder=True,
                         fileExtension=None
                         )

        db.session.add(new_file)
        db.session.commit()
    except:
        return jsonify({'msg': 'Błąd przy tworzeniu folderu!'})

    return jsonify({'msg': 'Folder stworzony'})


@app.route('/api/rename_file', methods=['POST'])
@token_required
def rename_file(current_user):

    file = request.form['file']
    newname = request.form['newname']
    PID = current_user.public_id
    files = Files.query.filter_by(public_id=PID).filter_by(uid=file).first()
    oldFileName = files.name
    rozszerzenie = oldFileName.split(".")[-1]
    WAI = files.wai
    newR = newname + '.' + rozszerzenie

    if newname != '':
        if files.isFolder:
            files.name = newname
        else:
            os.rename(os.path.abspath(os.path.join(os.sep, pathStore, PID+WAI, oldFileName)),
                      os.path.abspath(os.path.join(os.sep, pathStore, PID+WAI, newR)))
            files.name = newname + '.' + rozszerzenie

        db.session.commit()

        return jsonify({'msg': 'Nazwa pliku zmieniona'})

    return jsonify({'msg': 'Brak nazwy!'})


def retrieve_file_paths(dirName, myfiles, zipf, current_user, mywai):

    if myfiles.isFolder:
        for root, directories, files in os.walk(dirName):
            for filename in files:

                filePath = os.path.abspath(os.path.join(os.sep, root, filename))
                t = (mywai+myfiles.uid+'/')

                filesQ = Files.query.filter_by(public_id=current_user.public_id).all()
                index = filePath.index(myfiles.uid)
                shortFilePath = filePath[index:]
                shortFilePath = shortFilePath.replace(myfiles.uid, myfiles.name)

                for file in filesQ:
                    if (file.wai).startswith(t):
                        if file.isFolder:
                            shortFilePath.replace(file.uid, file.name)

                zipf.write(filePath, shortFilePath)
                zipf.printdir()
    else:
        filesQ = Files.query.filter_by(public_id=current_user.public_id).all()

        dname = dirName
        ndname = ''
        bdname = basename(dirName)
        nbdname = ''

        for file in filesQ:
            if file.uid == bdname:
                ndname = dname.replace(bdname, file.name)
        nbdname = basename(ndname)
        zipf.write(ndname, nbdname)

        return ''


@app.route('/api/download_files', methods=['POST'])
@token_required
def download_files(current_user):

    header = request.headers['downloadType']
    uids = request.form['files'].split(',')
    uid = []
    wai = json.loads(request.form['wai'])
    if header == 'regularDownload':
        for u in uids:
            fil = Files.query.filter_by(uid=u).first()
            uid.append(fil.uid)
            mywai = request.form['wai']
            files = Files.query.filter_by(public_id=current_user.public_id).all()
            if len(uids) == 1:
                for file in files:
                    if file.uid == uid[0]:
                        if file.isFolder:
                            path = os.path.abspath(os.path.join(os.sep, pathStore, file.public_id + jsonWAI(mywai), file.uid + '/'))
                            zip_file = zipfile.ZipFile((os.path.abspath(os.path.join(os.sep, pathStore, file.public_id, 'Store.zip'))), 'w', compression=zipfile.ZIP_DEFLATED)
                            retrieve_file_paths(path, file, zip_file, file, jsonWAI(mywai))
                            zip_file.close()

                            with open(os.path.abspath(os.path.join(os.sep, pathStore, file.public_id, 'Store.zip')),'rb') as z:
                                encode_string = base64.encodebytes(z.read())
                                res = Response(encode_string, headers={'name': 'Files', 'typ': 'application/zip'})
                                return res

                        else:
                            try:
                                with open(os.path.abspath(os.path.join(os.sep, pathStore, file.public_id + file.wai, file.name)),'rb') as f:
                                    encode_string = base64.encodebytes(f.read())
                                    res = Response(encode_string, headers={'name': file.name, 'typ': file.fileExtension})
                                    return res
                            except:
                                pass
                            try:
                                fn = (file.name).replace('_', ' ')
                                with open(os.path.abspath(os.path.join(os.sep, pathStore, file.public_id + file.wai, fn)), 'rb') as f:
                                    encode_string = base64.encodebytes(f.read())
                                    res = Response(encode_string,
                                                   headers={'name': file.name, 'typ': file.fileExtension})
                                    return res
                            except:
                                pass
            else:
                listtozip = []

                uid = []
                for u in uids:
                    for file in files:
                        if u == file.uid:
                            uid.append(file)


                for u in uid:
                    for file in files:
                        if u.uid == file.uid:
                            listtozip.append(file)
                try:
                    os.remove(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')))
                except:
                    pass

                zip_file = zipfile.ZipFile((os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip'))), 'a',
                                           compression=zipfile.ZIP_DEFLATED)

                for l in listtozip:
                    path = os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id + l.wai, l.uid))
                    retrieve_file_paths(path, l, zip_file, current_user, l.wai)

                zip_file.close()

                with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')), 'rb') as z:
                    encode_string = base64.encodebytes(z.read())
                    res = Response(encode_string, headers={'name': 'Files', 'typ': 'application/zip'})
                    return res



    if header == 'sharedDownload':
        if len(uids) == 1:
            try:
                files = Shared.query.filter_by(uid=uids[0]).first()
                fil = Files.query.filter_by(uid=files.share_uid).first()
                uid.append(fil.uid)
                if fil.isFolder:
                    path = os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id + fil.wai, fil.uid + '/'))
                    zip_file = zipfile.ZipFile((os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id, 'Store.zip'))), 'w',
                                               compression=zipfile.ZIP_DEFLATED)
                    retrieve_file_paths(path, fil, zip_file, fil, fil.wai)
                    zip_file.close()

                    with open(os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id, 'Store.zip')), 'rb') as z:
                        encode_string = base64.encodebytes(z.read())
                        res = Response(encode_string, headers={'name': 'Files', 'typ': 'application/zip'})
                        return res

                with open(os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id + fil.wai, fil.name)), 'rb') as f:
                    encode_string = base64.encodebytes(f.read())
                    res = Response(encode_string, headers={'name': fil.name, 'typ': fil.fileExtension})
                    return res
            except:
                pass

            try:
                fil = Files.query.filter_by(uid=uids[0]).first()
                uid.append(fil.uid)
                if fil.isFolder:
                    path = os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id + fil.wai, fil.uid + '/'))
                    zip_file = zipfile.ZipFile((os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id, 'Store.zip'))), 'w',
                                               compression=zipfile.ZIP_DEFLATED)
                    retrieve_file_paths(path, fil, zip_file, fil, fil.wai)
                    zip_file.close()

                    with open(os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id, 'Store.zip')), 'rb') as z:
                        encode_string = base64.encodebytes(z.read())
                        res = Response(encode_string, headers={'name': 'Files', 'typ': 'application/zip'})
                        return res

                with open(os.path.abspath(os.path.join(os.sep, pathStore, fil.public_id + fil.wai, fil.name)), 'rb') as f:
                    encode_string = base64.encodebytes(f.read())
                    res = Response(encode_string, headers={'name': fil.name, 'typ': fil.fileExtension})
                    return res
            except:
                pass

        else:
            if len(wai) == 1:
                files = Files.query.all()
                listtozip = []
                for u in uids:
                    x = Shared.query.filter_by(uid=u).first()
                    for file in files:
                        if x.share_uid == file.uid:
                            listtozip.append(file)
                try:
                    os.remove(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')))
                except:
                    pass

                zip_file = zipfile.ZipFile((os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip'))), 'a',
                                           compression=zipfile.ZIP_DEFLATED)
                for l in listtozip:
                    path = os.path.abspath(os.path.join(os.sep, pathStore, l.public_id + l.wai, l.uid))
                    retrieve_file_paths(path, l, zip_file, l, l.wai)

                zip_file.close()

                with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')), 'rb') as z:
                    encode_string = base64.encodebytes(z.read())
                    res = Response(encode_string, headers={'name': 'Files', 'typ': 'application/zip'})

                return res

            else:
                files = Files.query.all()
                listtozip = []
                for u in uids:
                    for file in files:
                        if u == file.uid:
                            listtozip.append(file)
                try:
                    os.remove(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')))
                except:
                    pass

                zip_file = zipfile.ZipFile((os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip'))), 'a',
                                           compression=zipfile.ZIP_DEFLATED)
                for l in listtozip:
                    path = os.path.abspath(os.path.join(os.sep, pathStore, l.public_id + l.wai, l.uid))
                    retrieve_file_paths(path, l, zip_file, l, l.wai)

                zip_file.close()

                with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')), 'rb') as z:
                    encode_string = base64.encodebytes(z.read())
                    res = Response(encode_string, headers={'name': 'Files', 'typ': 'application/zip'})

                return res


    if header == 'lastDownload':
        files = Files.query.filter_by(public_id=current_user.public_id).all()
        if len(uids) == 1:
            fil = Files.query.filter_by(uid=uids[0]).first()
            uid.append(fil.uid)
            for file in files:
                if file.uid == uid[0]:
                        with open(os.path.abspath(os.path.join(os.sep, pathStore, file.public_id + file.wai, file.name)), 'rb') as f:
                            encode_string = base64.encodebytes(f.read())
                            res = Response(encode_string, headers={'name': file.name, 'typ': file.fileExtension})
                            return res
        else:
            listtozip = []
            for u in uids:
                for file in files:
                    if u == file.uid:
                        listtozip.append(file)
            try:
                os.remove(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')))
            except:
                pass

            zip_file = zipfile.ZipFile((os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip'))), 'a',
                                       compression=zipfile.ZIP_DEFLATED)

            for l in listtozip:
                path = os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id + l.wai, l.uid))
                retrieve_file_paths(path, l, zip_file, current_user, l.wai)

            zip_file.close()

            with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'Store.zip')), 'rb') as z:
                encode_string = base64.encodebytes(z.read())
                res = Response(encode_string, headers={'name': 'Files', 'typ': 'application/zip'})
        return res


@app.route('/api/delete_file', methods=['POST'])
@token_required
def delete_file(current_user):

    data = request.form
    dataUID = data['file'].split(",")
    PID = current_user.public_id
    WAI = jsonWAI(data['wai'])
    WP_ID = PID+WAI

    files = Files.query.filter_by(public_id=PID).filter_by(wai=WAI).all()
    thisfiles = []
    try:
        for datafile in dataUID:
            for file in files:
                if datafile == file.uid:
                    thisfiles.append(file)

        files = Files.query.filter_by(public_id=PID).all()

        filesToDelete = []

        for file in thisfiles:
            filesToDelete.append(file)
            if file.isFolder:
                startSwitchWAI = file.wai + file.name + '/'
                for bfile in files:
                    if (bfile.wai).startswith(startSwitchWAI):
                        filesToDelete.append(bfile)

        try:
            for file in filesToDelete:
                path = os.path.abspath(os.path.join(os.sep, pathStore,WP_ID,file.name))
                if file.isFolder:
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        except:
            pass

        try:
            for file in filesToDelete:
                Files.query.filter_by(uid=file.uid).delete()
                try:
                    Shared.query.filter_by(share_uid=file.uid).delete()
                except:
                    pass
        except:
            pass

        db.session.commit()
    except:
        return jsonify({'msg': 'Błąd przy usuwaniu plików!'})

    return jsonify({'msg': 'Pliki usunięte'})


@app.route('/api/get_files', methods=['POST'])
@token_required
def get_files(current_user):

    waiData = jsonWAI(request.get_json()['wai'])
    files = Files.query.filter_by(public_id=current_user.public_id).filter_by(wai=waiData).all()
    out = []
    for file in files:

        file_data = {}
        file_data['uid'] = file.uid
        file_data['name'] = file.name
        file_data['datatime'] = str((file.data).strftime("%d/%m/%Y, %H:%M:%S"))
        file_data['isFolder'] = file.isFolder
        file_data['fileExtension'] = file.fileExtension
        out.append(file_data)

    return jsonify({'files': out})


# USER DETAIL

@app.route('/api/get_user_details', methods=['POST'])
@token_required
def get_user_details(current_user):
    out = []
    header = request.headers['Downloadtype']
    if header == 'detailNormal':
      u = User.query.filter_by(public_id=current_user.public_id).first()
    else:
        user = request.form['user']
        u = User.query.filter_by(public_id=user).first()

    #Nazwa
    file_data = {}
    file_data['name'] = 'Nazwa'
    file_data['detail'] = u.name
    out.append(file_data)

    #Role
    file_data = {}
    file_data['name'] = 'Ranga'
    if u.admin == True:
        file_data['detail'] = 'Admin'
    else:
        file_data['detail'] = 'Użytkownik'
    out.append(file_data)


    #Ilość plików
    file_data = {}
    file_data['name'] = 'Ilość plików'
    f = Files.query.filter_by(public_id=u.public_id).all()
    file_data['detail'] = len(f)
    out.append(file_data)

    #Ilość shared
    file_data = {}
    file_data['name'] = 'Udostępnione pliki dla mnie'
    s = Shared.query.filter_by(public_id=u.public_id).all()
    file_data['detail'] = len(s)
    out.append(file_data)

    #Ilość shared
    file_data = {}
    pd = []
    file_data['name'] = 'Moje pliki udostępnione'
    sf = Shared.query.all()
    ff = Files.query.all()

    for s in sf:
        for f in ff:
            if s.share_uid == f.uid:
                if f.public_id == u.public_id:
                   pd.append(f.public_id)

    file_data['detail'] = len(pd)
    out.append(file_data)


    #Ilość zdjęć
    file_data = {}
    file_data['name'] = 'Ilośc zdjęć'
    f = Files.query.filter_by(public_id=u.public_id).all()
    fa = []
    for f1 in f:
        str = f1.fileExtension
        try:
            if str.startswith('image'):
                fa.append(f1)
        except:
            pass
    file_data['detail'] = len(fa)
    out.append(file_data)

    #Ilość video
    file_data = {}
    file_data['name'] = 'Ilość plików wideo'
    f = Files.query.filter_by(public_id=u.public_id).all()
    fa = []
    for f1 in f:
        str = f1.fileExtension
        try:
            if str.startswith('video'):
                fa.append(f1)
        except:
            pass
    file_data['detail'] = len(fa)
    out.append(file_data)
    return jsonify({'details': out})



#//////////////////////////////////////////////////////////////////////////

#                       Last versions

#//////////////////////////////////////////////////////////////////////////



@app.route('/api/get_last_files', methods=['POST'])
@token_required
def get_last_files(current_user):
    files = Files.query.filter_by(public_id=current_user.public_id).all()
    out = []
    outdata = []
    for file in files:
        if file.isFolder == 0:
                        file_data = {}
                        file_data['uid'] = file.uid
                        file_data['name'] = file.name
                        file_data['datatime'] = (file.data)
                        outdata.append(file.data)
                        file_data['fileExtension'] = file.fileExtension
                        out.append(file_data)
    outdattime = []
    for outdat in outdata:
        outdattime.append((int(outdat.timestamp())))

    aftersorteddata = sorted(outdattime)
    readyarray = []

    for o in range(len(out)):
        for p in aftersorteddata:
            if(int(out[o]['datatime'].timestamp()) == p):
                readyarray.append(out[o])
                break


    newdata = []
    i = 1
    for ready in reversed(readyarray):
        file_data = {}
        file_data['uid'] = ready['uid']
        file_data['name'] = ready['name']
        file_data['datatime'] = (ready['datatime']).strftime("%d/%m/%Y, %H:%M:%S")
        file_data['fileExtension'] = ready['fileExtension']
        newdata.append(file_data)
        i += 1
        if i == 30:
            break

    return jsonify({'files': newdata})


@app.route('/api/get_file_show', methods=['POST'])
@token_required
def get_file_show(current_user):
    fuid = request.form['uid']
    files = Files.query.filter_by(uid=fuid).first()
    with open(os.path.abspath(os.path.join(os.sep, pathStore, files.public_id + files.wai, files.name)), 'rb') as bites:
        encode_string = base64.encodebytes(bites.read())
        my_j = encode_string.decode('utf-8')
        return my_j



#//////////////////////////////////////////////////////////////////////////

#                       Versions

#//////////////////////////////////////////////////////////////////////////



@app.route('/api/get_versions', methods=['POST'])
@token_required
def get_versions(current_user):

    file = request.form['file']
    versions = Versions.query.filter_by(public_id=current_user.public_id).filter_by(file_uid=file).all()
    outVersions = []

    for version in versions:
        verion_data = {}
        verion_data['uid'] = version.uid
        verion_data['file_uid'] = version.file_uid
        verion_data['message'] = version.message
        verion_data['datatime'] = str((version.data).strftime("%d/%m/%Y, %H:%M:%S"))
        verion_data['fileExtension'] = version.fileExtension
        outVersions.append(verion_data)
    try:
        fs = Files.query.filter_by(uid=versions[0].file_uid).first()
        verion_data = {}
        verion_data['uid'] = fs.uid
        verion_data['file_uid'] = 'null'
        verion_data['message'] = fs.message + '   <- Aktualna wersja'
        verion_data['datatime'] = str((fs.data).strftime("%d/%m/%Y, %H:%M:%S"))
        verion_data['fileExtension'] = fs.fileExtension
        outVersions.append(verion_data)
    except:
        pass

    reverseOutVersion = outVersions[::-1]

    return jsonify({'versions': reverseOutVersion})


@app.route('/api/add_version', methods=['POST'])
@token_required
def add_version(current_user):

    dataFile = request.files
    dataForm = request.form
    mainFileUID = dataForm['mainfile']
    awai = jsonWAI(dataForm['wai'])
    afile = dataFile['newversion']
    message = dataForm['message']

    path = os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id))
    if not git.Repo.init(path):
        git.Repo.init(path)
        repo = git.Repo(path)
        repo.git.add(A=True)
        repo.git.commit(m='start')

    repo = git.Repo(path)
    file = Files.query.filter_by(public_id=current_user.public_id).filter_by(uid=mainFileUID).first()
    print(file.name)
    print(file.message)
    path_dest_main_file = os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id + file.wai, file.name))

    # Sprawdzenie czy zgadzają się typy
    if file.fileExtension != afile.content_type:
        return jsonify({'msg': 'Zły typ'})

    # # Sprawdzenie czy nie są takie same
    # openFile = open(path_dest_main_file, 'rb')
    # if openFile.read() == afile.read():
    #     return jsonify({'msg': 'Ten sam plik'})

    ver = Versions.query.filter_by(public_id=current_user.public_id).filter_by(file_uid=dataForm['mainfile']).all()

    if len(ver) == 0:
        try:
            repo.git.add(A=True)
            repo.git.commit(m=file.name)
        except:
            pass

        # Tworzenie UID
        UID = str(uuid.uuid4())
        new_version = Versions(public_id=current_user.public_id,
                                 uid=UID,
                                 wai=file.wai,
                                 file_uid = file.uid,
                                 data=file.data,
                                 message='main',
                                 commit_id=repo.head.object.hexsha,
                                 fileExtension=file.fileExtension
                                 )

        db.session.add(new_version)
        db.session.commit()
        os.remove(path_dest_main_file)
        afile.stream.seek(0)
        afile.save(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id + awai, file.name)))
        repo.git.add(awai[1:] + file.name)
        repo.git.commit(m=message)

        file.data = datetime.datetime.now(pytz.timezone('Europe/Warsaw'))
        file.message = message
        file.commit_id = repo.head.object.hexsha
        db.session.commit()

    else:
        # Tworzenie UID
        # for v in ver:
        #     if v.commit_id == repo.head.object.hexsha:
        #         return jsonify('msg', 'commit powtorzony')

        UID = str(uuid.uuid4())
        new_version = Versions(public_id=current_user.public_id,
                                 uid=UID,
                                 wai=file.wai,
                                 file_uid = file.uid,
                                 data=file.data,
                                 message=file.message,
                                 commit_id=repo.head.object.hexsha,
                                 fileExtension=file.fileExtension
                                 )

        db.session.add(new_version)
        print(new_version)
        db.session.commit()

        os.remove(path_dest_main_file)
        afile.stream.seek(0)
        afile.save(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id + awai, file.name)))

        repo.git.add(awai[1:] + file.name)
        repo.git.commit(m=str(message))
        file.data = datetime.datetime.now(pytz.timezone('Europe/Warsaw'))
        file.message = message
        file.commit_id = repo.head.object.hexsha
        db.session.commit()

    return jsonify({'msg': 'Wersja dodana!'})


@app.route('/api/get_version_and_show', methods=['POST'])
@token_required
def get_version_and_show(current_user):

    auid = request.form['u1']
    mywai = request.form['wai']
    try:
        ver = Versions.query.filter_by(public_id=current_user.public_id).filter_by(uid=auid).first()
        commit_id = ver.commit_id
        file = Files.query.filter_by(public_id=current_user.public_id).filter_by(uid=ver.file_uid).first()

        path = os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id))
        repo = git.Repo(path)
        repo.git.checkout(commit_id)

        with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id+jsonWAI(mywai), file.name)), 'rb') as bites:
            encode_string = base64.encodebytes(bites.read())
            repo.git.checkout(file.commit_id)
            return encode_string
    except:
        pass
    try:
        file = Files.query.filter_by(public_id=current_user.public_id).filter_by(uid=auid).first()

        with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id+jsonWAI(mywai), file.name)), 'rb') as bites:
            encode_string = base64.encodebytes(bites.read())
            return encode_string
    except:
        pass



@app.route('/api/delete_version', methods=['POST'])
@token_required
def delete_version(current_user):

    data = request.form
    dataUID = data['file'].split(",")

    for data in dataUID:
        Versions.query.filter_by(uid=data).delete()

    db.session.commit()

    return jsonify({'msg': 'versje usuniete'})

@app.route('/api/download_version', methods=['POST'])
@token_required
def download_version(current_user):

    uid = request.form['file']
    mywai = request.form['wai']
    try:
        ver = Versions.query.filter_by(public_id=current_user.public_id).filter_by(uid=uid).first()
        file = Files.query.filter_by(public_id=current_user.public_id).filter_by(uid=ver.file_uid).first()

        path = os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id))

        repo = git.Repo(path)
        repo.git.checkout(ver.commit_id)

        with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id + jsonWAI(mywai), file.name)), 'rb') as f:
            encode_string = base64.encodebytes(f.read())
            res = Response(encode_string, headers={'name': file.name, 'typ': file.fileExtension})
            repo.git.checkout(file.commit_id)
            return res
    except:
        pass

    try:
        file = Files.query.filter_by(public_id=current_user.public_id).filter_by(uid=uid).first()

        with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id + jsonWAI(mywai), file.name)), 'rb') as f:
            encode_string = base64.encodebytes(f.read())
            res = Response(encode_string, headers={'name': file.name, 'typ': file.fileExtension})
            return res
    except:
        pass



#//////////////////////////////////////////////////////////////////////////

#                       Shared

#//////////////////////////////////////////////////////////////////////////


@app.route('/api/get_users', methods=['POST'])
@token_required
def get_users(current_user):

    users = User.query.all()
    out = []
    for user in users:
        # if user.public_id != current_user.public_id:
            file_data = {}
            file_data['name'] = user.name
            file_data['public_id'] = user.public_id
            if user.admin == True:
                file_data['role'] = 'Admin'
            else: file_data['role'] = 'Użytkownik'
            if user.avatar != None:
                av = user.avatar
                my_j = av.decode('utf-8')
                my_j = 'data:image/png;base64,' + my_j
                file_data['select'] = my_j
            else:
                with open(os.path.join('avatardefault'), 'rb') as z:
                    encode_string = base64.encodebytes(z.read())
                    my_j = encode_string.decode('utf-8')
                    my_j = 'data:image/png;base64,' + my_j
                    file_data['select'] = my_j

            out.append(file_data)

    return jsonify({'users': out})


@app.route('/api/add_shared_files', methods=['POST'])
@token_required
def add_shared_files(current_user):

    data = request.form

    files = data['files'].split(',')
    users = data['users'].split(',')


    for user in users:
        for file in files:
            juzUdostepnione = True
            file = Files.query.filter_by(uid=file).first()
            auser = User.query.filter_by(public_id=user).first()
            share = Shared.query.filter_by(public_id=auser.public_id).filter_by(share_uid=file.uid).all()
            if len(share) != 0:
                juzUdostepnione = False

            if juzUdostepnione:
                auid = str(uuid.uuid4())

                new_share = Shared(uid=auid,
                                   public_id=auser.public_id,
                                   share_uid=file.uid,
                                   fileExtension=file.fileExtension,
                                   isFolder=file.isFolder)

                db.session.add(new_share)
    try:
        db.session.commit()
    except:
        pass

    return jsonify({'msg': 'udostepniony'})




@app.route('/api/get_shared_files', methods=['POST'])
@token_required
def get_shared_files(current_user):

    mywai = request.form['wai']
    decodeWAI = jsonWAI(mywai)
    lwai = len(json.loads(mywai))

    if(lwai == 1):
        # try:
            shared_files = Shared.query.filter_by(public_id=current_user.public_id).all()
            if len(shared_files) != 0:
                out = []
                for shared_file in shared_files:
                    fs = Files.query.filter_by(uid=shared_file.share_uid).all()
                    for f in fs:
                        fpid = f.public_id
                        fname = f.name

                    u = User.query.filter_by(public_id=fpid).first()
                    uname = u.name

                    file_data = {}
                    file_data['uid'] = shared_file.uid
                    file_data['name'] = fname
                    file_data['datatime'] = str((shared_file.data).strftime("%d/%m/%Y, %H:%M:%S"))
                    file_data['isFolder'] = shared_file.isFolder
                    file_data['fileExtension'] = shared_file.fileExtension
                    file_data['owner'] = uname
                    out.append(file_data)
                return jsonify({'files': out})
            else:
                return jsonify({'msg': 'Brak plikow'})
        # except:
        #     return jsonify({'msg': 'Brak plikow2'})
    else:
        if (lwai == 2):
            uid_lastwai = json.loads(mywai)[lwai-1]['wai'][:-1]
            f = Files.query.filter_by(uid=uid_lastwai).first()
            pid = f.public_id
            u = User.query.filter_by(public_id=pid).first()
            files = Files.query.all()
            out = []


            for file in files:
                if (file.wai).endswith(decodeWAI):
                    file_data = {}
                    file_data['uid'] = file.uid
                    file_data['name'] = file.name
                    file_data['datatime'] = str((file.data).strftime("%d/%m/%Y, %H:%M:%S"))
                    file_data['isFolder'] = file.isFolder
                    file_data['fileExtension'] = file.fileExtension
                    file_data['owner'] = u.name
                    out.append(file_data)
            return jsonify({'files': out})
        else:
            nwai = decodeWAI.split('/')
            nnwai = len(nwai) - 2
            nnnwai = nwai[nnwai] + '/'
            files = Files.query.all()

            # owner

            own = nwai[2]
            f = Files.query.filter_by(uid=own).first()
            u = User.query.filter_by(public_id=f.public_id).first()
            o = u.name

            if (len(files)) != 0:
                out = []
                for file in files:
                    if (file.wai).endswith(nnnwai):
                        file_data = {}
                        file_data['uid'] = file.uid
                        file_data['name'] = file.name
                        file_data['datatime'] = str((file.data).strftime("%d/%m/%Y, %H:%M:%S"))
                        file_data['isFolder'] = file.isFolder
                        file_data['fileExtension'] = file.fileExtension
                        file_data['owner'] = o
                        out.append(file_data)
                return jsonify({'files': out})


@app.route('/api/get_file_to_show', methods=['POST'])
@token_required
def get_file_to_show(current_user):
    auid = request.form['uid']
    fileInfo = Files.query.filter_by(public_id=current_user.public_id).filter_by(uid=auid).first()
    mywai = request.form['wai']

    if fileInfo.isFolder:
        addPath = fileInfo.uid + '/'
        newJson = {'wai': addPath}
        waiList = json.loads((mywai))
        waiList.append(newJson)
        waiJson = json.dumps(waiList)
        return jsonify({'wai': waiJson})

    fn = (fileInfo.name).replace('_', ' ')

    try:
        with open(os.path.abspath(os.path.join(os.sep, pathStore, fileInfo.public_id+jsonWAI(mywai), fileInfo.name)), 'rb') as bites:
            encode_string = base64.encodebytes(bites.read())
            my_j = encode_string.decode('utf-8')
            return my_j
    except:
        pass

    try:
        with open(os.path.abspath(os.path.join(os.sep, pathStore, fileInfo.public_id+jsonWAI(mywai), fn)), 'rb') as bites:
            encode_string = base64.encodebytes(bites.read())
            my_j = encode_string.decode('utf-8')
            return my_j
    except:
        pass


@app.route('/api/get_shared_show', methods=['POST'])
@token_required
def get_shared_show(current_user):
    mywai = request.form['wai']
    auid = request.form['uid']
    lwai = len(json.loads(mywai))

    if (lwai == 1):
        sh = Shared.query.filter_by(public_id=current_user.public_id).filter_by(uid=auid).first()
        fileInfo = Files.query.filter_by(uid=sh.share_uid).first()
    else:
        try:
            sh = Shared.query.filter_by(uid=auid).first()
            fileInfo = Files.query.filter_by(uid=sh.share_uid).first()
        except:
            fileInfo = Files.query.filter_by(uid=auid).first()

    if fileInfo.isFolder:
        addPath = fileInfo.uid + '/'
        newJson = {'wai': addPath}
        waiList = json.loads((mywai))
        waiList.append(newJson)
        waiJson = json.dumps(waiList)
        return jsonify({'wai': waiJson})

    with open(os.path.abspath(os.path.join(os.sep, pathStore, fileInfo.public_id+fileInfo.wai, fileInfo.name)), 'rb') as bites:
        encode_string = base64.encodebytes(bites.read())
        my_j = encode_string.decode('utf-8')
        return my_j


@app.route('/api/delete_shared_files', methods=['POST'])
@token_required
def delete_shared_files(current_user):

    data = request.form
    files = data['file'].split(",")
    for file in files:
        Shared.query.filter_by(uid=file).delete()

    db.session.commit()

    return jsonify({'msg': 'Pliki usunięte'})



@app.route('/api/delete_user', methods=['POST'])
@token_required
def delete_user(current_user):

    data = request.form
    users = data['user'].split(',')
    if current_user.admin:
        for user in users:
            u = User.query.filter_by(public_id=user).first()
            if u.admin:
                return jsonify({'msg': 'Nie można usunąć admina'})
            else:
                User.query.filter_by(public_id=user).delete()

                try:
                    vs = Versions.query.filter_by(public_id=u.public_id).all()

                    for v in vs:
                        Versions.query.filter_by(uid=v.uid).delete()

                    sh = Shared.query.filter_by(public_id=u.public_id).all()

                    for s in sh:
                        Shared.query.filter_by(uid=s.uid).delete()

                    fs = Files.query.filter_by(public_id=u.public_id).all()

                    for f in fs:
                        Shared.query.filter_by(uid=f.uid).delete()

                    path = os.path.abspath(os.path.join(os.sep, pathStore, user))
                    shutil.rmtree(path)
                except:
                    pass

        db.session.commit()
        return jsonify({'msg': 'Użytkownik usunięty'})


@app.route('/api/change_role', methods=['POST'])
@token_required
def change_role(current_user):
    data = request.form['user']
    u = User.query.filter_by(public_id=data).first()
    if current_user.admin:
        if current_user.public_id == data:
            return jsonify({'msg': 'Nie możesz zmienić sam sobie rangi!'})
        if u.admin:
            u.admin = 0
        else:
            u.admin = 1

        get_users()
        db.session.commit()

    return jsonify({'msg': 'Ranga zmieniona'})


@app.route('/api/change_password', methods=['POST'])
@token_required
def change_password(current_user):

    data = request.form
    newpass = data['newpass']
    if newpass == 'undefined':
        return jsonify({'msg': 'Błąd przy zmianie hasła!'})
    u = User.query.filter_by(public_id=current_user.public_id).first()
    hashed_password = generate_password_hash(newpass, method='sha256')
    u.password = hashed_password
    db.session.commit()

    return jsonify({'msg': 'Hasło zmienione'})


@app.route('/api/change_password_admin', methods=['POST'])
@token_required
def change_password_admin(current_user):

    if current_user.admin:
        ps = request.form['newpass']
        if ps == 'undefined':
            return jsonify({'msg': 'Błąd przy zmianie hasła!'})
        us = request.form['user_id']
        u = User.query.filter_by(public_id=us).first()
        hashed_password = generate_password_hash(ps, method='sha256')
        u.password = hashed_password
        db.session.commit()

    return jsonify({'msg': 'Hasło zmienione'})


@app.route('/api/get_names', methods=['POST'])
@token_required
def getnames(current_user):

    bodyBreadCrumb = json.loads(request.form['bodyBreadCrumb'])
    lastBreadCrumb = json.loads(request.form['lastBreadCrumb'])

    files = Files.query.all()
    outBody = []

    for body in bodyBreadCrumb:
        for file in files:
            if body['wai'] == file.uid:
                outBody.append({'id': body['id'], 'wai': file.name})
    outBody.insert(0, {'id': 0, 'wai': 'All'})

    outLast = []

    for file in files:
        if lastBreadCrumb['wai'] == file.uid:
            outLast.append({'id': lastBreadCrumb['id'], 'wai': file.name})
    dumpOutBody = json.dumps(outBody)
    dumpOutLast = json.dumps(outLast)

    return jsonify({'dumpOutBody': dumpOutBody, 'dumpOutLast': dumpOutLast })


def add(self, key, value):
        self[key] = value


@app.route('/api/get_images', methods=['POST'])
@token_required
def get_images(current_user):
    mywai = jsonWAI(request.form['wai'])
    myfiles = []

    files = Files.query.filter_by(public_id=current_user.public_id).filter_by(wai=mywai).all()
    for file in files:
        try:
         if (file.fileExtension).startswith('image'):
                myfiles.append(file)
        except:
            pass

    width = 500
    height = 420
    encodefiles = []

    os.makedirs(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'imagesresize')), exist_ok=True)
    for myfile in myfiles:
        im1 = Image.open((os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id+mywai, myfile.name))))
        im2 = im1.resize((width, height), Image.NEAREST)
        name = myfile.name
        try:
            if name[-3:] == 'png':
                name = name[:-3] + 'jpeg'
        except:
            pass
        im3 = im2.convert('RGB')
        im3.save(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'imagesresize', name)))

        with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'imagesresize', name)), 'rb') as bites:
            encode_string = base64.encodebytes(bites.read())
            my_j = encode_string.decode('utf-8')
            my_j = 'data:image/jpg;base64,' + my_j
            s = json.dumps(my_j)
            encodefiles.append({'name': myfile.name, 'bit': my_j})

    shutil.rmtree(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'imagesresize')))



    return jsonify({'files': encodefiles})

@app.route('/api/profil', methods=['POST'])
@token_required
def profil(current_user):

    cu = current_user.name
    return jsonify({'name': cu})


@app.route('/api/add_avatar', methods=['POST'])
@token_required
def add_avatar(current_user):
    data = request.files['file']
    width = 100
    height = 100

    try:
        os.makedirs(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'avatar')), exist_ok=True)
        data.save(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'avatar', 'avatar.jpg')))
        im1 = Image.open((os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'avatar', 'avatar.jpg'))))
        im2 = im1.resize((width, height), Image.NEAREST)
        im3 = im2.convert('RGB')
        im3.save(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'avatar', 'ravatar.jpg')))

        with open(os.path.abspath(os.path.join(os.sep, pathStore, current_user.public_id, 'avatar', 'ravatar.jpg')), 'rb') as z:
            encode_string = base64.encodebytes(z.read())
            u = User.query.filter_by(public_id=current_user.public_id).first()
            u.avatar = encode_string
            db.session.commit()
        get_avatar()

    except:
        return jsonify({'msg': 'Błąd ze zdjęciem!'})


    return jsonify({'msg': 'Avatar dodany'})

@app.route('/api/get_avatar', methods=['POST'])
@token_required
def get_avatar(current_user):
    u = User.query.filter_by(public_id=current_user.public_id).first()
    if u.avatar != None:
        av = u.avatar
        my_j = av.decode('utf-8')
        my_j = 'data:image/jpg;base64,' + my_j
        return jsonify({'avatar': my_j})
    else:
        with open(os.path.join('avatardefault'), 'rb') as z:
            encode_string = base64.encodebytes(z.read())
            my_j = encode_string.decode('utf-8')
            my_j = 'data:image/png;base64,' + my_j
            return jsonify({'avatar': my_j})


@app.route('/api/isadmin', methods=['POST'])
@token_required
def isadmin(current_user):
    cu = current_user.admin
    return jsonify({'name': cu})


@app.route('/api/user', methods=['POST'])
@token_required
def get_all_users(current_user):

    if not current_user.admin:
        return jsonify({'message': 'Funkcja bład'})

    users = User.query.all()

    out = []

    for user in users:
        user_data = {}
        user_data['public_id'] = user.public_id
        user_data['name'] = user.name
        user_data['password'] = user.password
        user_data['admin'] = user.admin
        out.append(user_data)

    return jsonify({'users': out})



@app.route('/api/login',methods=['POST'])
def login():


    data = request.get_json()
    user = User.query.filter_by(name=data['name']).first()

    if not user:
        return jsonify({'msg':'Brak takiego użytkownika.'})

    if check_password_hash(user.password, data['password']):
        token = jwt.encode({'public_id': user.public_id,
                            'exp': datetime.datetime.now(pytz.timezone('Europe/Warsaw')) + datetime.timedelta(minutes=30)},
                           app.config['SECRET_KEY'])

        try:
            path = os.path.abspath(os.path.join(os.sep, pathStore, user.public_id))
            repo = git.Repo(path)
        except:
            git.Repo.init(path)
            repo.config_writer().set_value("user", "name", "myusername").release()
            repo.config_writer().set_value("user", "email", "myemail").release()

        return jsonify({'token': token.decode('UTF-8')})

    return jsonify({'msg':'Zła weryfikacja.'})



@app.route('/api/add_user', methods=['POST'])
@token_required
def add_user(current_user):
    data = request.form
    name = data['name']
    password = data['pass']
    if current_user.admin:
        if data['isadmin'] == 'true':
            isadmin = True
        else: isadmin = False

        users = User.query.all()
        for user in users:
            if str(user.name) == name:
                return jsonify({'msg':'Użytkownik o podanej nazwie już istnieje!'})
            if len(str(password)) < 6:
                return jsonify({'msg':'Hasło jest zbyt krótkie, minimum 6 znaków :)'})


        hashed_password = generate_password_hash(password, method='sha256')
        p_id = str(uuid.uuid4())
        new_user = User(public_id=p_id, name=name, password=hashed_password, admin=isadmin)

        path = os.path.abspath(os.path.join(os.sep, pathStore, p_id))
        git.Repo.init(path)
        try:
            repo = git.Repo(path)
            repo.config_writer().set_value("user", "name", "myusername").release()
            repo.config_writer().set_value("user", "email", "myemail").release()
        except:
            pass
        db.session.add(new_user)
    db.session.commit()

    return jsonify({'msg': 'Użytkownik dodany!'})


if __name__ == '__main__':
    app.run()
