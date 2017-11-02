import configparser
import itertools
import logging
import os
import time
from threading import Event

import click
from sleekxmpp import ClientXMPP
from sleekxmpp.xmlstream import ET


class VacBot(ClientXMPP):
    def __init__(self, user, domain, resource, secret, vacuum):
        ClientXMPP.__init__(self, user + '@' + domain, '0/' + resource + '/' + secret)

        self.user = user
        self.domain = domain
        self.resource = resource
        self.vacuum = vacuum
        self.credentials['authzid'] = user
        self.add_event_handler("session_start", self.session_start)

        self.ready_flag = Event()

    def wait_until_ready(self):
        self.ready_flag.wait()

    def session_start(self, event):
        print("----------------- starting session ----------------")
        self.ready_flag.set()

    def send_command(self, action):
        c = self.wrap_command(action.to_xml())
        c.send()

    def wrap_command(self, ctl):
        q = self.make_iq_query(xmlns=u'com:ctl', ito=self.vacuum + '/atom',
                               ifrom=self.user + '@' + self.domain + '/' + self.resource)
        q['type'] = 'set'
        for child in q.xml:
            if child.tag.endswith('query'):
                child.append(ctl)
                return q

    def connect_and_wait_until_ready(self):
        self.connect(('47.88.66.164', '5223'))  # TODO: change to domain name
        click.echo("starting")
        self.process()
        click.echo("done with process")
        self.wait_until_ready()

    def run(self, action):
        click.echo("running " + str(action))
        self.send_command(action)
        if action.wait:
            click.echo("sleeping for " + str(action.wait) + "s")
            time.sleep(action.wait)


class VacBotCommand():
    def __init__(self, name, args, wait=None, terminal=False):
        self.name = name
        self.args = args
        self.wait = wait
        self.terminal = terminal

    def to_xml(self):
        clean = ET.Element(self.name, self.args)
        ctl = ET.Element('ctl', {'td': self.name.capitalize()})
        ctl.append(clean)
        return ctl


class Clean(VacBotCommand):
    def __init__(self, wait):
        super().__init__('clean', {'type': 'auto', 'speed': 'standard'}, wait)


class Charge(VacBotCommand):
    def __init__(self):
        super().__init__('charge', {'type': 'go'}, terminal=True)


def read_config(filename):
    parser = configparser.ConfigParser()
    with open(filename) as fp:
        parser.read_file(itertools.chain(['[global]'], fp), source=filename)
    return parser['global']


@click.group(chain=True)
@click.option('--charge/--no-charge', default=True, help='Return to charge after running. Defaults to yes.')
@click.option('--debug/--no-debug', default=False)
def cli(charge, debug):
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s %(message)s')


@cli.command(help='cleans for the specified number of minutes')
@click.argument('minutes', type=click.FLOAT)
def clean(minutes):
    return Clean(minutes * 60)


@cli.command(help='returns to charger')
def charge():
    return Charge()


@cli.resultcallback()
def run(actions, charge, debug):
    config = read_config(os.path.expanduser('~/.config/sucks.conf'))
    vacbot = VacBot(config['user'], config['domain'], config['resource'], config['secret'],
                    config['vacuum'])
    vacbot.connect_and_wait_until_ready()
    for action in actions:
        vacbot.run(action)
    if charge and not actions[-1].terminal:
        vacbot.run(Charge())
    vacbot.disconnect(wait=True)


if __name__ == '__main__':
    cli()