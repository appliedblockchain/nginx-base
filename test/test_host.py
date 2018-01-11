#!/usr/bin/python3
import Pyro4
import time
import logging
from functools import reduce
from plumbum import local, BG, cli
from test_utils import parseStat, getVarnishPids, getNginxPids, getMemUsage, humanReadableSize

logger = logging.getLogger("test-host")
logger.setLevel(logging.INFO)
h = logging.StreamHandler()
fmt = logging.Formatter("%(asctime)s: %(message)s")
h.setFormatter(fmt)
logger.addHandler(h)

report_logger = logging.getLogger("test-report")
report_logger.setLevel(logging.INFO)
report_logger.addHandler(h)
h  = logging.FileHandler("test_report.txt")
h.setFormatter(fmt)
report_logger.addHandler(h)


class ClientProcess(object):

    host_cmd = local["python3"]["test/client_process.py"]
    def __init__(self):
        self._host = ClientProcess.host_cmd & BG
        uri = self._host.proc.stdout.readline().decode('ascii').strip()
        logger.debug ("Process spawned, Pyro4 uri: {}".format(uri))
        self._cmd = Pyro4.Proxy(uri)

    def uri(self):
        return self._uri

    def kill(self):
        self._host.proc.kill()

    def cmd(self):
        return self._cmd

class TestApplication(cli.Application):
    connections = cli.SwitchAttr(['-c'], int, default = 1, help = "Number of connections per instance" )
    instances = cli.SwitchAttr(['-i'], int, default = 3, help = "Number of instances to spawn" )
    delay = cli.SwitchAttr(['-d'], int , default = 1, help = "Delay in seconds for probing test results")
    packet_size = cli.SwitchAttr(['-s'], int, default = 10 ** 3, help = "Size of websocket frame")
    ws_server = cli.SwitchAttr(['-w'], str, default = "127.0.0.1:8080", help = "Websocket server host[:port]")
    iteration = cli.SwitchAttr(['--iterations'], int,  default = 10, help = "Number of test results probing iterations")

    def main(self):
        def calcTotalMem(mems):
            return "{}K".format(reduce(lambda x, y: x + int(y.replace('K','')), mems, 0))

        self.procs = []
        start_time  = time.time()
        nginx_pids = getNginxPids()
        varnish_pids = getVarnishPids()
        report_logger.info("Inital memory usage:")
        nginx_init_mem = getMemUsage(nginx_pids)
        varnish_init_mem = getMemUsage(varnish_pids)
        report_logger.info("Total: Nginx: {}, Varnish: {}".format(
                            calcTotalMem(nginx_init_mem), calcTotalMem(varnish_init_mem)))
        report_logger.info("Per process: Nginx: {}, Varnish: {}".format(nginx_init_mem, varnish_init_mem))
        logger.info("Spawning workers")
        for i in range(0, self.instances):
            self.procs.append(ClientProcess())
        logger.info("Opening connections")
        for proc in self.procs:
            proc.cmd().init(self.connections, "ws://{}/streaming".format(self.ws_server), self.packet_size, 0.3)
        logger.info("Starting workers")
        for proc in self.procs:
            proc.cmd().start()
        report_logger.info("Monitoring stats")
        try:
            def getStat():
                frames = data = 0
                for proc in self.procs:
                    stats = proc.cmd().stat()
                    frames += stats[0]
                    data += stats[1]
                return frames, data

            for i in range(0, self.iteration):
                logger.info("Wait {} sec".format(self.delay))
                tm = time.time()
                time.sleep(self.delay)
                logger.info("Pausing")
                for proc in self.procs:
                    cmd = proc.cmd()
                    cmd.pause()
                    (cmd.stat())
                logger.info("Gathering stat") 
                frames, data = getStat()
                report_logger.info("{} time from last report: {:.1f} seconds {}".format(
                                   5 * '-', time.time() - tm, 5 * '-'))
                report_logger.info("Frames: {}, Bytes: {}({})".format(
                                    frames, humanReadableSize(data), data, ))
                stat = parseStat(self.ws_server)
                report_logger.info("Reported:")
                report_logger.info("Frames: {}, Bytes: {}({}), Webscoket connections: {}".format(
                                    stat[1], humanReadableSize(stat[2]), stat[2], stat[0]))

                if(nginx_pids != getNginxPids()):
                        report_logger.warn("one or more of the nginx process has been restarted")
                        nginx_pids = getNginxPids()
                
                nginx_mem = getMemUsage(nginx_pids)
                varnish_mem = getMemUsage(varnish_pids)
                report_logger.info("Mem usage:")
                report_logger.info("Total: Nginx: {}, Varnish: {}".format(
                                    calcTotalMem(nginx_mem), calcTotalMem(varnish_mem)))
                report_logger.info("Per worker: Nginx: {}, Varnish: {}".format(nginx_mem, varnish_mem))
                logger.info("Unpausing")
                for proc in self.procs:
                    cmd = proc.cmd()
                    cmd.unpause()
            logger.info ("Stopping worker threads")
            for proc in self.procs:
                cmd = proc.cmd()
                cmd.stop_proc()
            logger.info("Gathering stat") 
            frames, data = getStat()
            report_logger.info ("Frames: {}, Bytes: {}({}), total time elapsed: {:0.1f} seconds".format(
                                 frames, humanReadableSize(data), data, time.time()-start_time))
            stat = parseStat(self.ws_server)
            report_logger.info("Reported:")
            report_logger.info("Frames: {}, Bytes: {}({})".format(
                                stat[1], humanReadableSize(stat[2]), stat[2]))
            nginx_mem = getMemUsage(nginx_pids)
            varnish_mem = getMemUsage(varnish_pids)
            report_logger.info("Total memory usage at start:")
            report_logger.info("Nginx: {}, Varnish: {}".format(
                                calcTotalMem(nginx_init_mem), calcTotalMem(varnish_init_mem)))
            nginx_mem = getMemUsage(nginx_pids)
            varnish_mem = getMemUsage(varnish_pids)
            report_logger.info("Memory usage now:")
            report_logger.info("Nginx: {}, Varnish: {}".format(
                                calcTotalMem(nginx_mem), calcTotalMem(varnish_mem)))

        finally:
            logger.info("Terminating worker process")
            for proc in self.procs:
                proc.kill()
            logger.info("Done")
TestApplication.run()