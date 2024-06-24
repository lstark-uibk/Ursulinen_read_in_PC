from PyQt5.QtWidgets import QApplication,  QLineEdit, QCheckBox, QHBoxLayout, QLabel ,QWidget, QMainWindow, QPushButton,QFileDialog, QVBoxLayout, QInputDialog,QComboBox
import matplotlib.pyplot
matplotlib.use('Qt5Agg')
from PyQt5 import QtCore
from PyQt5.QtCore import *
from PyQt5.QtGui import QFont
import pyqtgraph as pg
import sys
import os
import datetime as dt
import numpy as np
import time
import glob
import logging
import pandas as pd
from pyflightdata import FlightData
import pytz
import traceback
import re
from naneos.iotweb import download_from_iotweb

fp_logging = r"C:\Users\c7441354\Documents\Ursulinen\Data_airport\logging"
time_now = dt.datetime.now()
filename = f"logging_microphone_{time_now.strftime('%Y-%m-%d_%H_%M_%S')}.log"
loggingfp = os.path.join(fp_logging,filename)
logging.basicConfig(
    filename=loggingfp,
    encoding='utf-8',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
print(f"Logging in {loggingfp}")

class Partector():
    def __init__(self):
        # now with default values
        self.serial_number =  "8300"
        self.column_names = ['Time_UNIX', 'Amplitude']
        self.data = pd.DataFrame(columns=self.column_names)
        self.download_data_last_hour()

    def download_data_last_hour(self):
        TOKEN = "sC3nkb7BZGQVwPLMSXZouqswMoajcvF1ppYEJXRR8E6NOEXWZunfdIV1x0MILK19bQKpKXZJ3rXyrnkIrvKDaw=="

        time_now = dt.datetime.now()
        start = time_now-dt.timedelta(hours=1)

        name = "leanderstark"
        print(f"Download data from naneos IoT {start} - {time_now}")

        df = download_from_iotweb(name, self.serial_number, start , time_now, TOKEN)
        df["Time_UNIX"] = (df.index-pd.Timestamp("1970-01-01",tz="UTC")) // pd.Timedelta("1s")
        df = df.rolling(5).mean().dropna()
        self.data = df



class Microphone():
    def __init__(self,Save_directory):
        # now with default values
        self.save_directory = Save_directory
        self.column_names = ['Time_UNIX', 'Amplitude']
        self.data = pd.DataFrame(columns=self.column_names)
        self.try_update_data()

    def try_update_data(self):
        self.data = pd.DataFrame(columns=self.column_names)
        files = self.save_directory + "\\*"
        all_files_mic = np.array(glob.glob(files))
        datetime_files = [re.search(re.compile(r'\d{4}_\d{2}_\d{2}_\d{2}h\d{2}m'), path).group().replace('h', ':').replace('m', '')
                          for path in all_files_mic]
        datetime_files = np.array([dt.datetime.strptime(date, '%Y_%m_%d_%H:%M') for date in datetime_files], dtype='datetime64')

        time_now = dt.datetime.now()
        lasttwohoursfiles = all_files_mic[datetime_files > time_now - dt.timedelta(hours=2)]
        print(f"Try do load data from {lasttwohoursfiles}")
        for fp in lasttwohoursfiles:
            df = pd.read_csv(fp,index_col = 0)
            df = df.rolling(5).mean().dropna()
            df["Time"] = pd.to_datetime(df.Time_UNIX,unit = "s")
            self.data = pd.concat([self.data,df])
        print(f"data in shape {self.data.shape}")
class Flightdata():
    """
    The data is stored in self.data as an xarray with coordinates time, flightdata
    The time dimesion is scheduled time
    Flightdata is all *str: [time_estimated_UNIX, time_real_UNIX", "time_scheduled_UNIX", "status", "origin", "destination", "aircraftmodel",
                            "aircraftmodel_code", "callsign", "airline", "arrival_departure"]
    And is "" if no data is given
    """
    def __init__(self):
        self.data = []
        self.vlines = {}
        self.get_flightdata()

    def extract_relevant_data(self, flightdata_array, arrival_or_departure):
        nrflights = len(flightdata_array)
        time_coordinates = np.empty(nrflights, dtype="datetime64[s]")
        flight_movement_info = {"default_identification": [""] * nrflights,
                                "time_scheduled_UNIX_departure": [""]*nrflights,
                                "time_scheduled_UNIX_arrival": [""] * nrflights,
                                "time_estimated_UNIX_departure": [""]*nrflights,
                                "time_estimated_UNIX_arrival": [""] * nrflights,
                                "time_real_UNIX_arrival": [""]*nrflights,
                                "time_real_UNIX_departure": [""] * nrflights,
                                "time_best_UNIX": [""]*nrflights,
                                "status" : [""]*nrflights,
                                "origin": [""]*nrflights,
                                "destination": [""]*nrflights,
                                "aircraftmodel": [""]*nrflights,
                                "aircraftmodel_code": [""]*nrflights,
                                "callsign": [""]*nrflights,
                                "airline": [""]*nrflights,
                                "arrival_departure": [""]*nrflights,
                                }
        for index, flight in enumerate(flightdata_array):
            flight_movement_info["arrival_departure"][index] = arrival_or_departure
            for arrdep in ["arrival","departure"]:
                flight_movement_info[f"time_scheduled_UNIX_{arrdep}"][index] = flight["flight"]["time"]["scheduled"][f"{arrdep}_millis"]/1000
                if arrdep == arrival_or_departure:
                    flight_movement_info["time_best_UNIX"][index] = flight_movement_info[f"time_scheduled_UNIX_{arrival_or_departure}"][index]

                try:
                    flight_movement_info[f"time_estimated_UNIX_{arrdep}"][index] = flight["flight"]["time"]["scheduled"][f"{arrdep}_millis"] / 1000
                    if arrdep == arrival_or_departure:
                        flight_movement_info[f"time_best_UNIX_{arrdep}"][index] = flight_movement_info[f"time_estimated_UNIX_{arrdep}"][index]
                except:
                    flight_movement_info[f"time_estimated_UNIX_{arrdep}"][index] = ""
                try:
                    flight_movement_info[f"time_real_UNIX_{arrdep}"][index] = flight["flight"]["time"]["real"][f"{arrdep}_millis"] / 1000
                    if arrdep == arrival_or_departure:
                        flight_movement_info["time_best_UNIX"][index] =   flight_movement_info[f"time_real_UNIX_{arrdep}"][index]

                except:
                    flight_movement_info[f"time_real_UNIX_{arrdep}"][index] = ""

            for z in ["origin", "destination"]:
                try:
                    flight_place = flight["flight"]["airport"][z]["code"]["iata"]
                    flight_movement_info[z][index] = flight_place
                except:
                    flight_movement_info[z][index] = ""
            try:
                flight_movement_info["aircraftmodel"][index]= flight["flight"]["aircraft"]["model"]["text"]
                flight_movement_info["aircraftmodel_code"][index] = flight["flight"]["aircraft"]["model"]["code"]
                flight_movement_info["callsign"][index] = flight["flight"]["identification"]["callsign"]
                flight_movement_info["status"][index] = flight["flight"]["status"]["text"]

            except:
                flight_movement_info["aircraftmodel"][index] = ""
                flight_movement_info["callsign"][index] = ""
                flight_movement_info["aircraftmodel_code"][index] = ""
                flight_movement_info["status"][index] = ""

            try:
                flight_movement_info["airline"][index] = flight["flight"]["airline"]["name"]
            except:
                flight_movement_info["airline"][index] = ""
            try:
                flight_movement_info["default_identification"][index] = flight["flight"]["identification"]["number"]["default"]
            except:
                flight_movement_info["default_identification"][index] = ""

        flight_movement_info = pd.DataFrame(flight_movement_info)
        flight_movement_info.index = flight_movement_info["time_best_UNIX"].astype(int)

        return flight_movement_info
    def get_flightdata(self):
        print("Try to get Flight data")
        f = FlightData()
        arrivals_alldata = f.get_airport_arrivals('INN',earlier_data = True)
        departures_alldata = f.get_airport_departures('INN',earlier_data = True)

        arrivals = self.extract_relevant_data(arrivals_alldata, "arrival")
        departures = self.extract_relevant_data(departures_alldata, "departure")
        flight_movements = pd.concat([arrivals,departures])
        flight_movements = flight_movements.sort_index()
        self.data = flight_movements
        return flight_movements


class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [dt.fromtimestamp(value) for value in values]

class MainPlot(pg.PlotWidget):
    def __init__(self, *args, **kwargs):
        super(MainPlot, self).__init__(*args, **kwargs)
        self.setBackground("w")
        self.showGrid(x=True, y=True)

        self.showAxis('right')
        self.vb2 = pg.ViewBox()
        self.plotItem.scene().addItem(self.vb2)
        self.getAxis('right').linkToView(self.vb2)
        self.vb2.setXLink(self)
        self.getAxis('right').setLabel('axis2', color='#0000ff')

        self.updateViews()

        self.plotItem.vb.sigResized.connect(self.updateViews)

    def updateViews(self):
        self.vb2.setGeometry(self.plotItem.vb.sceneBoundingRect())
        self.vb2.linkedViewChanged(self.plotItem.vb, self.vb2.XAxis)
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amplitude read in")
        #self.save_location = str(QFileDialog.getExistingDirectory(self, "Wo speicher ich die Daten hin?"))
        self.save_location = "C:\\Users\\c7441354\\Documents\\Ursulinen\\Data_airport\\microphone"
        #self.save_location = "F:\\Uniarbeit\\data\\test"
        print(f"Get data from {self.save_location}")

        self.reload_every_s = 4
        self.file_ndatapoints = 60*60
        self.secondsback = 60*60
        self.flight = Flightdata()
        self.mic = Microphone(self.save_location)
        self.part = Partector()


        # initiate ui
        self.init_ui()
        #multithreading
        self.threadpool = QThreadPool()


        #update data every second
        self.timer_onesec = QtCore.QTimer()
        self.timer_onesec.setInterval(self.reload_every_s*1000)
        self.timer_onesec.timeout.connect(self.timer_function)
        print("starting timer")
        self.timer_onesec.start()


    def init_ui(self):
        print("Initializing Window")
        self.setGeometry(0,0,1000,1000)
        mainlayout = QVBoxLayout()

        pg.setConfigOptions(antialias=True)
        self.graphWidget = MainPlot()
        mainlayout.addWidget(self.graphWidget)

        self.timewindow_combobox = QComboBox()
        self.timewindow_combobox.addItems(["1 h","30min","5 min","1 min"])
        mainlayout.addWidget(self.timewindow_combobox)
        self.timewindow_combobox.currentIndexChanged.connect(self.timewindow_combobox_changed)

        widget = QWidget()
        widget.setLayout(mainlayout)
        self.setCentralWidget(widget)

    # here updating the plot in a seperate thread makes the program unstable!
    def timer_function(self):
        print(f"thread {self.threadpool.activeThreadCount()}: replot.")
        self.mic.try_update_data()
        self.part.download_data_last_hour()
        self.update_plot()


    def timewindow_combobox_changed(self, index):
        self.index = index
        if self.index == 0:
            self.secondsback = 60*60
        elif self.index == 1:
            self.secondsback = 60*30
        elif self.index == 2:
            self.secondsback = 60*5
        elif self.index == 3:
            self.secondsback = 60
        print(f"plotte jetzt {self.secondsback}s zurück")

    def remove_all_plot_items(self,Graphwidget):
        for item in Graphwidget.allChildItems():
            Graphwidget.removeItem(item)



    def update_plot(self):
        # self.remove_all_plot_items(self.graphWidget)
        self.graphWidget.clear()
        part_numb = self.part.data.particle_number_concentration.values
        part_diam = self.part.data.average_particle_diameter.values
        part_time = self.part.data.Time_UNIX.values
        self.graphWidget.plot(part_time,part_numb,pen=pg.mkPen((13, 77, 181), width=1.5))

        time_mic = self.mic.data.Time_UNIX.values
        ampl = self.mic.data.Amplitude.values
        miccurve = pg.PlotCurveItem(time_mic, ampl,pen=pg.mkPen((224, 49, 18), width=1.5))
        self.graphWidget.vb2.addItem(miccurve)
        diametercurve = pg.PlotCurveItem(part_time,part_diam,pen=pg.mkPen((250, 163, 15), width=1.5))
        self.graphWidget.vb2.addItem(diametercurve)
        y_min_ax1 = 0
        y_max_ax1 = np.max(part_numb)*1.1
        y_min_ax2 = 0
        y_max_ax2 = np.max(ampl)*1.1
        x_min = time_mic[-1] - self.secondsback
        x_max = time_mic[-1] + self.secondsback/4
        self.graphWidget.setYRange(y_min_ax1, y_max_ax1)
        self.graphWidget.setXRange(x_min, x_max)

        # vlines for flights
        self.flight.vlines = {}
        print(int(x_min),int(x_max))
        selected_flight_data = self.flight.data[(self.flight.data.time_best_UNIX >x_min) & (self.flight.data.time_best_UNIX <x_max)]
        print(selected_flight_data)
        for arrdep,color,vonnach  in zip(["arrival", "departure"],["r","b"],["von","nach"]):
            arrdep_data = selected_flight_data[selected_flight_data.arrival_departure == arrdep]
            for time_index, row in arrdep_data.iterrows():
                best_time = int(row.time_best_UNIX)
                label = f"{dt.datetime.fromtimestamp(best_time).strftime('%H:%M')} Flug {row.default_identification} {vonnach} {row.origin}, Status: {row.status}"
                print(f"{best_time} with {label}")
                labelOpts = {"position": 0,  # 0.8 - len(compound_name)* 0.01,
                             "rotateAxis": (1, 0),
                             "anchors": [(0, 0), (0, 0)],
                             "color": 'k',
                             }
                vline = pg.InfiniteLine(pos = best_time, angle = 90, movable= False,pen=pg.mkPen(color, width=2), label = label,labelOpts= labelOpts)
                vline.label.setFont(QFont('Arial', 15))

                self.graphWidget.addItem(vline)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
