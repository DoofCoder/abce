from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, Markup
import webbrowser
from os.path import isfile
import os
import pandas as pd
import pygal as pg
from collections import OrderedDict
from abce.webtext import abcedescription

DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

app = Flask(__name__)
app.config.from_object(__name__)

inputs = []
simulation = None
gtitle = 'ABCE Simulation'
gtext = abcedescription
opened = False

def newest_subdirectory(directory='.'):
    directory = os.path.abspath(directory)
    all_subdirs = [os.path.join(directory, name)
                   for name in os.listdir(directory)
                   if os.path.isdir(os.path.join(directory, name))]
    return  max(all_subdirs, key=os.path.getmtime) + '/'

@app.route('/')
def show_entries():
    return render_template('show_entries.html', entries=inputs, title=gtitle, text=gtext)

@app.route('/submitted_simulation', methods=['POST'])
def submitted_simulation():
    parameters = {}
    form = request.form.to_dict()
    for element in inputs:
        name = element['name']
        if element['type'] == bool:
            parameters[name] = name in form
        elif element['type'] == str:
            try:
                parameters[name] = eval(form[name])
            except:
                parameters[name] = form[name].replace('\n','').replace('\r', '').lstrip().rstrip()
        else:
            parameters[name] = element['type'](form[name])
    simulation(parameters)
    return redirect(url_for('show_simulation'))

@app.route('/show_simulation')
def show_simulation():
    output = []
    path = newest_subdirectory('./result')
    for filename in os.listdir(path):
        if filename[-4:] == '.csv':
            df = pd.read_csv(path + filename)
            if (filename.startswith('aggregate_')
                    or filename.endswith('_aggregate.csv')
                    or filename.endswith('_mean.csv')):
                for c in df.columns:
                    if c not in ['index', 'round']:
                        graph = pg.Line()
                        graph.add(c, df[c])
                        output.append({'idname': str(hash(filename + c))[0:12],
                                       'title': filename[:-4] + ' ' + c,
                                       'graph': graph.render(is_unicode=True)
                                       })

            elif filename.startswith('panel_'):
                maxid = max(df['id']) + 1
                for c in df.columns:
                    if c not in ['index', 'round', 'id']:
                        graph = pg.Line()
                        for id in range(maxid):
                            graph.add(str(id), df[c][df['id'] == id])
                        output.append({'idname': str(hash(filename + c))[0:12],
                                       'title': filename[:-4] + ' ' + c,
                                       'graph': graph.render(is_unicode=True)
                                       })
    return render_template('show_outcome.html', entries=output)



def generate(new_inputs, new_simulation, names=None, title=None, text=None):
    global inputs
    global simulation
    global gtitle
    global gtext
    simulation = new_simulation

    ordered_inputs = OrderedDict()
    ordered_inputs['name'] = new_inputs.pop('name', 'name')
    ordered_inputs.update(new_inputs)
    try:
        del ordered_inputs['trade_logging']
    except KeyError:
        pass
    ordered_inputs['trade_logging'] = ['off', 'individual', 'group']

    for parameter, value in ordered_inputs.items():
        element = {}
        element['name'] = parameter
        element['value'] = value
        try:
            element['title'] = names[parameter]
        except (TypeError, KeyError):
            element['title'] = parameter
        if type(value) == tuple:
            lvalue = sorted(value)
            element['min'] = lvalue[0]
            element['default'] = lvalue[1]
            element['max'] = lvalue[2]
        elif type(value) is float or type(value) is int:
            element['min'] = 0
            element['default'] = value
            element['max'] = value * 2

        if type(value) == tuple or type(value) is float or type(value) is int:
            if type(element['default']) is int and type(element['max']) is int:
                element['step'] = 1
                element['type'] = int
            else:
                element['type'] = float
                element['step'] = (element['max'] - element['min']) / 100

            content = """  {title}
                            <div class="mdl-grid">
                                <div class="mdl-cell mdl-cell--8-col">
                                    <input class="mdl-slider mdl-js-slider" type="range"
                                        min="{min}" max="{max}" value="{default}" id="sl{name}"
                                        step="{step}" oninput="change_text_field(this.value, '{name}')"
                                        onchange="change_text_field(this.value, '{name}')">
                                    </input>
                                </div>
                                <div class="mdl-cell mdl-cell--3-col">
                                    <div class="mdl-textfield mdl-js-textfield">
                                        <input class="mdl-textfield__input" type="text" id="{name}" name="{name}"
                                            onchange="change_slider_field(this.value, 'sl{name}')"
                                            value="{default}">
                                        </input>
                                    </div>
                                </div>
                            </div>""".format(**element)
        elif type(value) is bool:
            element['type'] = bool
            content = """<div>{title}</div><br> <label class="mdl-switch mdl-js-switch mdl-js-ripple-effect" for="{name}">
                          <input type="checkbox" id="{name}" class="mdl-switch__input" name={name} checked>
                          <span class="mdl-switch__label"></span>
                        </label>""".format(**element)
        elif type(value) is list:  # menu
            assert_all_of_the_same_type(value)
            element['type'] = type(value[0])
            element['value0'] = value[0]
            content = ("""<div>{title}</div><br><input list="{name}" value="{value0}" name="{name}">
                            <datalist id="{name}"> """
                      + "".join(['<option value="%s">' % item for item in value])
                      + """ </datalist> """).format(**element)
        elif type(value) is str:  # menu
            element['type'] = str
            content = """<div>{title}</div>
                         <div class="mdl-textfield mdl-js-textfield">
                           <textarea class="mdl-textfield__input" type="text"
                             rows= "1" id="{name}" name="{name}">{value}</textarea>
                           <label class="mdl-textfield__label" for="{name}">{value}</label>
                         </div>""".format(**element)
        elif value is None:
            content = parameter
        else:  # field
            raise SystemExit(str(value) + "not recognized")
        element['content'] = content
        if value is not None:
            inputs.append(element)


def run(open=True, new=1):
    """ runs the web interface that starts the ABCE simulation. If open=True,
    (default) it opens a new window in the web browser if false you need to
    manually go to  http://127.0.0.1:5000/"""
    if not opened:
        if open:
            if inputs:
                webbrowser.open("http://127.0.0.1:5000/", new=new, autoraise=True)
            else:
                webbrowser.open("http://127.0.0.1:5000/show_simulation", new=new, autoraise=True)
            global opened
        else:
            if inputs:
                print "go to http://127.0.0.1:5000/"
            else:
                print "go to http://127.0.0.1:5000/show_simulation"
        opened = True
        app.run(use_reloader=False)

# slider (slider-range)
# switch
# field
# menu (editable) (options)
# menu (fixed) (options)
# text

def assert_all_of_the_same_type(value):
    for item in value:
        if type(item) != type(value[0]):
            raise ValueError("all list values must be of the same type. If 5.5"
                             " is used 0.0 instead of 0 must be used: " + str(value))


if __name__ == '__main__':
    app.run()