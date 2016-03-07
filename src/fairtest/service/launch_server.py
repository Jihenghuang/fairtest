"""
Demo server
"""
import os
import yaml


from flask import Flask
from flask import url_for
from flask import request
from flask import Response
from flask import redirect
from flask import send_file
from flask import render_template
from flask import send_from_directory

from werkzeug import secure_filename

import logging
from rq import Queue
from flask import abort
from redis import Redis
from tempfile import mkdtemp, mkstemp


def load_config(config):
    config = os.path.join("config", config)
    with open(config, 'r') as config_file:
        return yaml.load(config_file)


CONF = load_config("./config.yaml")
HOSTNAME = CONF['redis_hostname']
PORT = CONF['redis_port']
REDIS_CONN = Redis(host=HOSTNAME, port=PORT)
REDIS_QUEUE = Queue(connection=REDIS_CONN)
DATASETS_FOLDER = '/tmp/fairtest/datasets'
EXPERIMENTS_FOLDER = '/tmp/fairtest/experiments'
ALLOWED_EXTENSIONS = set(['csv', 'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])


def allowed_file(filename):
    """
    Assert file tupes
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def list_features(filename):
  """
  Helper getting features from csv header
  """
  with open(filename, "r") as f:
    head = []
    try:
      for line in f:
        head = line.rstrip().split(',')
        break
    except Exception, error:
      print "Exception:", error
    return head


def make_tree(path, metadata=False):
    """
    List directory contents
    """
    tree = dict(name=os.path.basename(path), children=[])
    try: lst = os.listdir(path)
    except OSError:
        pass #ignore errors
    else:
        for name in lst:
            fn = os.path.join(path, name)
            if os.path.isdir(fn):
                tree['children'].append(make_tree(fn))
            else:
              MAX = 10
              features = []
              if metadata:
                features = "(Features: " + ', '.join(list_features(fn)[:MAX])
                if len(list_features(fn)) > MAX:
                  features += " ..."
                features += ")"

              tree['children'].append({'name': name, 'metadata': features})
    return tree


app = Flask(__name__, static_folder='/tmp')
app.config['DATASETS_FOLDER'] = DATASETS_FOLDER
app.config['EXPERIMENTS_FOLDER'] = EXPERIMENTS_FOLDER


from helpers import experiments

@app.route('/fairtest', methods=['GET', 'POST'])
def handler():
    """
    This is the main handler entry point
    """
    # POST request may require some work
    if request.method == 'POST':

        inv = None
        out = None
        sens = None
        upload_file = None
        expl = None
        report = None
        dataset = None

        # retrieve fields with set values
        try:
            upload_file = request.files['file']
        except Exception, error:
          pass
        try:
            dataset = request.form['dataset']
        except Exception, error:
            pass
        try:
            sens = request.form['sens']
        except Exception, error:
            pass
        try:
            expl = request.form['expl']
        except Exception, error:
            pass
        try:
            out = request.form['out']
        except Exception, error:
            pass
        try:
            inv = request.form['inv']
        except Exception, error:
            pass
        try:
            report = request.form['report']
        except Exception, error:
            pass

        # 1. upload  file(dataset registration)
        if upload_file:
            if upload_file and allowed_file(upload_file.filename):
                filename = secure_filename(upload_file.filename)
                upload_file.save(os.path.join(app.config['DATASETS_FOLDER'], filename))

        # 2. post a new experiment
        if dataset:
            dataset = os.path.join(app.config['DATASETS_FOLDER'], dataset)
            experiment_dict = {'dataset': dataset,
                'sens': sens,
                'expl': expl,
                'inv': inv,
                'out': out,
                'experiments_folder': EXPERIMENTS_FOLDER
            }
            print experiment_dict
            REDIS_QUEUE.enqueue(experiments.demo_run, experiment_dict)

    return render_template("upload.html",
                           tree1=make_tree(app.config['DATASETS_FOLDER'], metadata=True),
                           datasets_folder=app.config['DATASETS_FOLDER'],
                           tree2=make_tree(app.config['EXPERIMENTS_FOLDER']),
                           experiments_folder=app.config['EXPERIMENTS_FOLDER'])


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
