#!/usr/bin/python
# -*- coding: utf-8 -*-
#author : zhangdawang
#data:2017-7-9
import pandas as pd
import numpy as np
import pyexcel_xls
import datetime
import copy
import warnings
import random
warnings.filterwarnings("ignore")

#对excel表格中的数据进行处理
def GetOriginData():
    excel_data = pyexcel_xls.get_data("data/厦航大赛数据20170705_1.xlsx")

    #["航班ID", "日期", "国际/国内", "航班号", "起飞机场", "降落机场", "起飞时间", "降落时间", "飞机ID", "机型", "重要系数"]
    Flight = pd.DataFrame(excel_data['航班'][1:], 
        columns = ["flightId", "date", "isDomestic", "flightNo", "startAirport", "endAirport", "startDateTime", "endDateTime", "airplaneId", "airplaneType", "importRatio"])
    #["起飞机场", "降落机场", "飞机ID"]
    AirplaneLimitation = pd.DataFrame(excel_data['航线-飞机限制'][1:], 
        columns = ["startAirport", "endAirport", "airplaneId"])
    #["机场", "关闭时间", "开放时间", "生效日期", "失效日期"]
    AirportClose = pd.DataFrame(excel_data['机场关闭限制'][1:], 
        columns = ["airport", "beginCloseTime", "endCloseTime", "beginDate", "endDate"])
    #["开始时间", "结束时间", "故障类型", "机场", "航班ID", "飞机ID"]
    Scene = pd.DataFrame(excel_data['台风场景'][1:], 
        columns = ["startDateTime", "endDateTime", "type", "airport"])
    #["机型", "起飞机场", "降落机场", "飞行时间"]
    TravelTime = pd.DataFrame(excel_data['飞行时间'][1:],
        columns = ["airplaneType", "startAirport", "endAirport", "travelTime"])
    Scene = Scene.fillna(0)
    #对航班进行飞机序号与开始时间的排序
    Flight = Flight.sort_values(['airplaneId', 'startDateTime'])
    Flight = Flight.reset_index(drop = True)
    return Flight, AirplaneLimitation, AirportClose, Scene, TravelTime

#判断是否宵禁, False表示没有宵禁
def IsAirportClose(AirportCloseD, airport, DateTime):
    if not airport in AirportCloseD:
        return False
    else:
        for l in AirportCloseD[airport]:
            if DateTime.time() > l[0] and DateTime.time() < l[1] and DateTime.date() >= l[2] and DateTime.date() <= l[3]:
                return True
        return False

#构建初始解
def GetInitialSolution(Flight, Scene, AirportCloseD, hour):
    Flight['isCancel'] = 0
    affectedAirport = set(Scene['airport'])
    delayD = {0: 0}
    delayDcompare = {0: 0}
    #确定哪些航班需要取消, 1是因为不能飞，2是因为不能降
    for i in Flight.index:
        if Flight['startAirport'][i] in affectedAirport:
            #prepareTime = min(datetime.timedelta(minutes = 50), Flight['startDateTime'][i] - Flight['endDateTime'][i - 1])
            if Flight['startDateTime'][i] > Scene[Scene['airport'] == Flight['startAirport'][i]][Scene['type'] == "起飞"]['startDateTime'].iloc[0]\
            and Flight['startDateTime'][i] < Scene[Scene['airport'] == Flight['startAirport'][i]][Scene['type'] == "起飞"]['endDateTime'].iloc[0]:
                Flight['isCancel'][i] = 1
        elif Flight['endAirport'][i] in affectedAirport:
            if Flight['endDateTime'][i] > Scene[Scene['airport'] == Flight['endAirport'][i]][Scene['type'] == "降落"]['startDateTime'].iloc[0]\
            and Flight['endDateTime'][i] < Scene[Scene['airport'] == Flight['endAirport'][i]][Scene['type'] == "降落"]['endDateTime'].iloc[0]:
                Flight['isCancel'][i] = 2

    DomesticJoint = {}
    l = 0
    for i in Flight.index:
        if i == 2363:
            continue
        if Flight['isCancel'][i] != 0 or Flight['isCancel'][i + 1] != 0:
            if not Flight['isDomestic'][i] == "国内":
                continue
            if Flight['date'][i] == Flight['date'][i + 1] and Flight['flightNo'][i] == Flight['flightNo'][i + 1]:
                if Flight['endAirport'][i] in (49, 50, 61):
                    DomesticJoint[Flight['flightId'][i]] = Flight['flightId'][i + 1]

    #找出可以提前的航班,将其变为可飞
    FlightDismissList = []
    done = 0
    airplaneNow = 0
    for i in Flight.index:
        if Flight['airplaneId'][i] != airplaneNow:
            done = 0
            airplaneNow = Flight['airplaneId'][i]
        elif done == 0:
            #提前无法起飞的飞机
            if Flight['isCancel'][i] == 1 and Flight['isDomestic'][i] == "国内":
                startTime = Scene[Scene['airport'] == Flight['startAirport'][i]][Scene['type'] == "起飞"]['startDateTime'].iloc[0]
                advancedTime = Flight['startDateTime'][i] - startTime
                if advancedTime <= datetime.timedelta(hours = 6) and Flight['endDateTime'][i - 1] + datetime.timedelta(minutes = 50) <= Flight['startDateTime'][i] - advancedTime:
                    #print(Flight['airplaneId'][i], Flight['flightId'][i])
                    Flight['isCancel'][i] = 0
                    #delayD[Flight['flightId'][i]] = - advancedTime
                    Flight['startDateTime'][i] = Flight['startDateTime'][i] - advancedTime
                    Flight['endDateTime'][i] = Flight['endDateTime'][i] - advancedTime
                    Flight['importRatio'][i] = Flight['importRatio'][i] * (1 - 0.15 * advancedTime / datetime.timedelta(hours = 1))
                    done = 1
                elif advancedTime <= datetime.timedelta(hours = 6) and Flight['endDateTime'][i - 1] + datetime.timedelta(minutes = 50) > Flight['startDateTime'][i] - advancedTime:
                    #delayD[Flight['flightId'][i]] = - advancedTime
                    if Flight['date'][i] == Flight['date'][i - 1] and Flight['flightNo'][i] == Flight['flightNo'][i - 1]:
                        continue
                    if Flight['date'][i] == Flight['date'][i + 1] and Flight['flightNo'][i] == Flight['flightNo'][i + 1]:
                        if not (Flight['startAirport'][i + 1] in (49, 50, 61) or Flight['endAirport'][i + 1] in (49, 50, 61)):
                            continue
                    Flight['startDateTime'][i] = Flight['startDateTime'][i] - advancedTime
                    Flight['endDateTime'][i] = Flight['endDateTime'][i] - advancedTime
                    Flight['importRatio'][i] = Flight['importRatio'][i] * (1 - 0.15 * advancedTime / datetime.timedelta(hours = 1))
                    FlightDismissList.append([[airplaneNow, Flight['airplaneType'][i], 0, 0], [Flight['flightId'][i]]])
                    print(Flight['startDateTime'][i])

    # #停机限制，将机场无法起飞的飞机前一航班取消
    # airplaneNow = 0
    # for i in Flight.index:
    #     if Flight['airplaneId'][i] != airplaneNow:
    #         airplaneNow = Flight['airplaneId'][i]
    #     else:
    #         if Flight['isCancel'][i] == 1 and Flight['isCancel'][i - 1] == 0:
    #             Flight['isCancel'][i - 1] = 3
    Flight = Flight.sort_values(['airplaneId', 'startDateTime'])
    Flight = Flight.reset_index(drop = True)
    #找出可以推迟的航班，将其变为可飞, 推迟时间为2h,仅将那些推迟后不会宵禁的航班串推迟,包括无法降落或者无法起飞的飞机
    airplaneNow = 0
    delayhours = hour
    for i in Flight.index:
        index = 0
        if Flight['airplaneId'][i] != airplaneNow:
            airplaneNow = Flight['airplaneId'][i]
        else:
            if Flight['isCancel'][i] == 0 and (Flight['startAirport'][i] in set(Scene['airport'])):
                comparetime = Scene[Scene['airport'] == Flight['startAirport'][i]][Scene['type'] == "起飞"]['endDateTime'].iloc[0]
                delaytime = datetime.timedelta(minutes = 50) + comparetime - Flight['startDateTime'][i]
                if delaytime > datetime.timedelta(minutes = 0) and delaytime <= datetime.timedelta(minutes = 50):
                    #首先判断是否有宵禁取消航班
                    j = i
                    index = 0
                    delaytimecopy = delaytime
                    while(Flight['airplaneId'][j] == airplaneNow):
                        starttime = Flight['startDateTime'][j] + delaytimecopy
                        endtime = Flight['endDateTime'][j] + delaytimecopy
                        delaytimecopy = max(datetime.timedelta(minutes = 0), delaytimecopy - max(datetime.timedelta(minutes = 0), Flight['startDateTime'][j + 1] - Flight['endDateTime'][j] - datetime.timedelta(minutes = 50)))
                        if IsAirportClose(AirportCloseD, Flight['startAirport'][j], starttime) or IsAirportClose(AirportCloseD, Flight['endAirport'][j], endtime):
                            index = 1
                            break
                        j += 1      
                    #若没有宵禁取消航班
                    if index == 0:
                        j = i
                        while(Flight['airplaneId'][j] == airplaneNow):
                            delayD[Flight['flightId'][j]] = delaytime
                            starttime = Flight['startDateTime'][j] + delaytime
                            endtime = Flight['endDateTime'][j] + delaytime
                            delaytime = max(datetime.timedelta(minutes = 0), delaytime - max(datetime.timedelta(minutes = 0), Flight['startDateTime'][j + 1] - Flight['endDateTime'][j] - datetime.timedelta(minutes = 50)))

                            #print(Flight['flightId'][j], Flight['airplaneId'][j])
                            Flight['isCancel'][j] = 0
                            Flight['startDateTime'][j] = starttime
                            Flight['endDateTime'][j] = endtime
                            j += 1
                    else:
                        Flight['isCancel'][i] = 4
            else:
                delaytime = datetime.timedelta(hours = delayhours + 1)
                if Flight['isCancel'][i] == 1:
                    endtime = Scene[Scene['airport'] == Flight['startAirport'][i]][Scene['type'] == "起飞"]['endDateTime'].iloc[0]
                    delaytime = datetime.timedelta(minutes = 50) + endtime - Flight['startDateTime'][i]
                if Flight['isCancel'][i] == 2:
                    delaytime = Scene[Scene['airport'] == Flight['endAirport'][i]][Scene['type'] == "降落"]['endDateTime'].iloc[0]- Flight['startDateTime'][i]
                if delaytime <= datetime.timedelta(hours = delayhours):
                    #首先判断是否有宵禁取消航班
                    j = i
                    index = 0
                    delaytimecopy = delaytime
                    while(Flight['airplaneId'][j] == airplaneNow):
                        starttime = Flight['startDateTime'][j] + delaytimecopy
                        endtime = Flight['endDateTime'][j] + delaytimecopy
                        delaytimecopy = max(datetime.timedelta(minutes = 0), delaytimecopy - max(datetime.timedelta(minutes = 0), Flight['startDateTime'][j + 1] - Flight['endDateTime'][j] - datetime.timedelta(minutes = 50)))
                        if IsAirportClose(AirportCloseD, Flight['startAirport'][j], starttime) or IsAirportClose(AirportCloseD, Flight['endAirport'][j], endtime):
                            index = 1
                            break
                        j += 1
                    #若没有宵禁取消航班
                    if index == 0:
                        j = i
                        while(Flight['airplaneId'][j] == airplaneNow):
                            delayD[Flight['flightId'][j]] = delaytime
                            if Flight['isCancel'][j] != 0:
                                if Flight['startAirport'][j] in (49, 50, 61):
                                    delayDcompare[Flight['flightId'][j]] = Scene.ix[0][1] + datetime.timedelta(minutes = 50) - Flight['startDateTime'][j]
                                else:
                                    delayDcompare[Flight['flightId'][j]] = Scene.ix[0][1] - Flight['endDateTime'][j]
                            starttime = Flight['startDateTime'][j] + delaytime
                            endtime = Flight['endDateTime'][j] + delaytime
                            delaytime = max(datetime.timedelta(minutes = 0), delaytime - max(datetime.timedelta(minutes = 0), Flight['startDateTime'][j + 1] - Flight['endDateTime'][j] - datetime.timedelta(minutes = 50)))
                            #print(Flight['flightId'][j], Flight['airplaneId'][j])
                            Flight['isCancel'][j] = 0
                            Flight['startDateTime'][j] = starttime
                            Flight['endDateTime'][j] = endtime
                            j += 1
    #找出航班是否为联程航班
    JointD = {}
    k = 2
    for i in Flight[Flight['isCancel'] == 0].index:
        if (Flight['date'][i], Flight['flightNo'][i]) in JointD:
            JointD[(Flight['date'][i], Flight['flightNo'][i])] = k
            k += 1
        else:
            JointD[(Flight['date'][i], Flight['flightNo'][i])] = 0

    JoinD_cancel = {}
    for i in Flight[Flight['isCancel'] != 0].index:
        if (Flight['date'][i], Flight['flightNo'][i]) in JoinD_cancel:
            JoinD_cancel[(Flight['date'][i], Flight['flightNo'][i])].append(Flight["flightId"][i])
        else:
            JoinD_cancel[(Flight['date'][i], Flight['flightNo'][i])] = [Flight["flightId"][i]]
    Flight = Flight.sort_values(['airplaneId', 'startDateTime'])
    Flight = Flight.reset_index(drop = True)
    #构建飞行航班字典
    #飞行航班字典，里面包含航班的前一个航班的最晚到达时间，是否为联程航班，起始时间，到达时间，起始机场，到达机场,  重要系数
    FlightD = {}
    airplaneNow = 0
    isJoint = 0
    starttimes = []
    endtimes = []
    for i in Flight.index:
        isJoint = JointD.get((Flight['date'][i], Flight['flightNo'][i]), 1)
        canceljointflight = JoinD_cancel.get((Flight['date'][i], Flight['flightNo'][i]), []).copy()
        if len(canceljointflight) == 2:
            canceljointflight.remove(Flight["flightId"][i])
        else:
            canceljointflight = [0]

        if Flight['airplaneId'][i] != airplaneNow:
            needArriveTime = Flight['startDateTime'][i] - datetime.timedelta(minutes = 50)
            starttimes.append(Flight['startDateTime'][i] - delayD.get(Flight['flightId'][i], datetime.timedelta(minutes = 0)))
            endtimes.append(Flight['endDateTime'][i] - delayD.get(Flight['flightId'][i], datetime.timedelta(minutes = 0)))
            FlightD[Flight['flightId'][i]] = [needArriveTime, isJoint] + [starttimes[-1], endtimes[-1]] +list(Flight.ix[i][['startAirport', 'endAirport', 'importRatio', 'airplaneType', 'isCancel']]) + canceljointflight + [0]
            airplaneNow = Flight['airplaneId'][i]
        else:
            needArriveTime = max(Flight['startDateTime'][i] - datetime.timedelta(minutes = 50), Flight['endDateTime'][i - 1])
            starttimes.append(Flight['startDateTime'][i] - delayD.get(Flight['flightId'][i], datetime.timedelta(minutes = 0)))
            endtimes.append(Flight['endDateTime'][i] - delayD.get(Flight['flightId'][i], datetime.timedelta(minutes = 0)))
            FlightD[Flight['flightId'][i]] = [needArriveTime, isJoint] + [starttimes[-1], endtimes[-1]] + list(Flight.ix[i][['startAirport', 'endAirport', 'importRatio', 'airplaneType', 'isCancel']]) + canceljointflight + [0]
    Flight['startDateTime'] = starttimes
    Flight['endDateTime'] = endtimes

    #可执行航班,包含正常航班与初始解中去除必取消的航班
    #正常航班包括：[使用飞机号，飞机类型, 飞机当前机场, 包含尾串数量]，[航班串或者航班环]
    #取消航班包括: [原使用飞机号，原使用飞机类型, 是否为尾班]， [航班串或者航班环]
    FlightExecuteList = []
    airplaneNow = 0
    dismiss = 0
    ferryFlightNum = 0
    initialCost = 0

    dimisscost = 0
    for i in Flight.index:
        if Flight['isCancel'][i] != 0:
            dimisscost += Flight['importRatio'][i] * 1000


    for i in Flight.index:
        if Flight['isCancel'][i] != 0:
            initialCost += Flight['importRatio'][i] * 1000
        #换飞机时   
        if Flight['airplaneId'][i] != airplaneNow:
            #如果dismiss为0，也就是都没有取消
            if dismiss == 0 and i != 0:
                FlightExecuteList[-1][0][3] = 1
            #判断是否是尾班
            if FlightDismissList and FlightDismissList[-1][0][0] == airplaneNow:
                ferryFlightNum += 1
                FlightDismissList[-1][0][2] = 1
                FlightDismissList[-1][0][3] = Flight['endAirport'][i - 1]
            if Flight['isCancel'][i] != 0:
                airplaneNow = Flight['airplaneId'][i]
                dismiss = 1
                FlightExecuteList.append([[airplaneNow, Flight['airplaneType'][i], Flight['startAirport'][i], 0], []])
            else:
                airplaneNow = Flight['airplaneId'][i]
                dismiss = 0
                FlightExecuteList.append([[airplaneNow, Flight['airplaneType'][i], Flight['startAirport'][i], 0], [Flight['flightId'][i]]])
        else:
            if dismiss == 0:
                if Flight['isCancel'][i] != 0:
                    dismiss = 1
                else:
                    FlightExecuteList[-1][1].append(Flight['flightId'][i])
            else:
                if Flight['isCancel'][i] == 0 and Flight['isCancel'][i - 1] == 0:
                    FlightDismissList[-1][1].append(Flight['flightId'][i])
                    initialCost += Flight['importRatio'][i] * 1000
                elif Flight['isCancel'][i] == 0:
                    FlightDismissList.append([[airplaneNow, Flight['airplaneType'][i], 0, 0], [Flight['flightId'][i]]])
                    initialCost += Flight['importRatio'][i] * 1000
    FlightDismissList[-1][0][2] = 1


    print("Dismiss flight number is:", Flight[Flight['isCancel'] != 0].shape[0])
    print("Dismiss cost is:", dimisscost)
    #计算初始费用, 提前航班的暂时不计
    initialCost += ferryFlightNum * 5000
    print("Initial Answer Has done, cost: ", initialCost)
    return FlightD, FlightExecuteList, FlightDismissList, initialCost, delayD, Flight, DomesticJoint, delayDcompare

#得到国内航班集合, 飞行时间字典，航线飞机限制集合
def GetSets(Flight, TravelTime, AirplaneLimitation, AirportClose):
    DomesticSet = set()
    for i in Flight.index:
        if Flight['isDomestic'][i] == "国内":
            DomesticSet.add(Flight['startAirport'][i])
            DomesticSet.add(Flight['endAirport'][i])

    FlytimeD = {}
    for i in TravelTime.index:
        FlytimeD[tuple(TravelTime.ix[i][["airplaneType", "startAirport", "endAirport"]])] = TravelTime['travelTime'][i]

    AirplaneLimit = set()
    for i in AirplaneLimitation.index:
        AirplaneLimit.add(tuple(AirplaneLimitation.ix[i]))

    AirportCloseD = {}
    for i in AirportClose.index:
        if AirportClose['airport'][i] in AirportCloseD:
            AirportCloseD[AirportClose['airport'][i]].append(list(AirportClose.ix[i][1:]))
        else:
            AirportCloseD[AirportClose['airport'][i]] = [list(AirportClose.ix[i])[1:]]
    #AirportCloseD[6][0][0] = AirportCloseD[6][0][0].time()
    return DomesticSet, FlytimeD, AirplaneLimit, AirportCloseD

def transTime(time):
    str_minute = "0" + str(time.minute)
    return str(time.year) + "/" + str(time.month) + "/" + str(time.day) + " " + str(time.hour) + ":" + str_minute[-2:]

def generateResult(Flight):
    Flight['isFerry'] = 0
    ResultFlight = Flight[['flightId', 'startAirport', 'endAirport', 'startDateTime', 'endDateTime', 'airplaneId', 'isCancel', 'isStraight', 'isFerry']]
    startDateTime = []
    endDateTime = []
    isFerry = []
    isCancel = []
    for i in ResultFlight.index:
        if i%1000 == 0:
            print("transhasdone:", i)
        startDateTime.append(transTime(Flight['startDateTime'][i]))
        endDateTime.append(transTime(Flight['endDateTime'][i]))
        if ResultFlight['flightId'][i] > 2364:
            isFerry.append(1)
        else:
            isFerry.append(0)
        if Flight['isCancel'][i] != 0:
            isCancel.append(1)
        else:
            isCancel.append(0)
    ResultFlight['startDateTime'] = startDateTime
    ResultFlight['endDateTime'] = endDateTime
    ResultFlight['isCancel'] = isCancel
    ResultFlight['isFerry'] = isFerry
    return ResultFlight
    #return ResultFlight[['flightId', 'startAirport', 'endAirport', 'startDateTime', 'endDateTime', 'airplaneId', 'isCancel', 'isStraight', 'isFerry']]

def Getdelayflight(Flight, FlightD, delayD, FlightDismissList, AirportCloseD):
    #将10h内的飞机给拿出来
    for i in Flight.index:
        if Flight['isCancel'][i] != 0:
            if Flight['date'][i] == Flight['date'][i - 1] and Flight['flightNo'][i] == Flight['flightNo'][i - 1]:
                continue
            if Flight['startAirport'][i] in (49, 50, 61):
                delaytime = Scene.ix[0][1] - Flight['startDateTime'][i] + datetime.timedelta(minutes = 50)
            else:
                delaytime = Scene.ix[0][1] - Flight['endDateTime'][i]
            if delaytime > datetime.timedelta(hours = 10):
                continue
            starttime = Flight['startDateTime'][i] + delaytime
            endtime = Flight['endDateTime'][i] + delaytime
            if IsAirportClose(AirportCloseD, Flight['startAirport'][i], starttime) or IsAirportClose(AirportCloseD, Flight['endAirport'][i], endtime):
                continue
            f = Flight['flightId'][i]
            delayD[f] = delaytime
            FlightDismissList.append([[0, FlightD[f][7], 0, 0], [f]])
            Flight['isCancel'][i] = 0

            j = i + 1
            while Flight['isCancel'][j] != 0:
                delaytime = max(datetime.timedelta(minutes = 0), delaytime - max(datetime.timedelta(minutes = 0), Flight['startDateTime'][j + 1] - Flight['endDateTime'][j] - datetime.timedelta(minutes = 50)))
                starttime = Flight['startDateTime'][j] + delaytime
                endtime = Flight['endDateTime'][j] + delaytime
                if IsAirportClose(AirportCloseD, Flight['startAirport'][j], starttime) or IsAirportClose(AirportCloseD, Flight['endAirport'][j], endtime):
                    if (Flight['date'][j] == Flight['date'][j - 1] and Flight['flightNo'][j] == Flight['flightNo'][j - 1]):
                        Flight['isCancel'][j] = 0
                        break
                print("***")
                delayD[Flight['flightId'][j]] = delaytime
                FlightDismissList[-1][1].append(Flight['flightId'][j])
                Flight['isCancel'][j] = 0
                j += 1
    return FlightD, delayD, FlightDismissList

#**************************************************
#获得一个航班列表中的航班环
def findFlightCycle(FlightD, FlightList):
    if not FlightList:
        return []
    #所有起始机场，与最后一班的结束机场
    startport = []
    FlightCycle = []
    for flight in FlightList:
        startport.append(FlightD[flight][4])
    startport.append(FlightD[FlightList[-1]][5])
    #寻找所有子串
    dport = {}
    for i in range(len(startport)):
        if startport[i] in dport:
            dport[startport[i]].append(i)
        else:
            dport[startport[i]] = [i]
    for key in dport:
        temp = dport[key]
        ltemp = len(temp)
        if ltemp < 2:
            continue
        else:
            for i in range(ltemp):
                for j in range(ltemp - 1, i, -1):
                    if temp[j] - temp[i] >= 2:
                        FlightCycle.append(FlightList[temp[i]: temp[j]])
    return FlightCycle

#获得两个航班列表中，具有相同起始机场与结束机场的航班串
def findSameStartEnd(FlightD, FlightList1, FlightList2):
    if not FlightList1 or not FlightList2:
        return []
    #所有起始机场，与最后一班的结束机场
    startports1 = []
    for flight in FlightList1:
        startports1.append(FlightD[flight][4])
    startports1.append(FlightD[FlightList1[-1]][5])

    startports2 = []
    for flight in FlightList2:
        startports2.append(FlightD[flight][4])
    startports2.append(FlightD[FlightList2[-1]][5])

    l1, l2 = len(startports1), len(startports2)
    d1 = {}
    for i in range(l1):
        for j in range(i + 1, l1):
            if (startports1[i], startports1[j]) in d1:
                d1[(startports1[i], startports1[j])].append([i, j])
            else:
                d1[(startports1[i], startports1[j])] = [[i, j]]

    d2 = {}
    for i in range(l2):
        for j in range(i + 1, l2):
            if (startports2[i], startports2[j]) in d2:
                d2[(startports2[i], startports2[j])].append([i, j])
            else:
                d2[(startports2[i], startports2[j])] = [[i, j]]
    res = []
    for key in d1:
        if key in d2:
            for list1 in d1[key]:
                for list2 in d2[key]:
                    res.append([list1, list2])
    return res

#寻找两个航班列表中，具有相同起始机场的航班尾串
def findSameStartport(FlightD, FlightList1, FlightList2):
    if not FlightList1 or not FlightList2:
        return []

    l1, l2 = len(FlightList1), len(FlightList2)
    startports1 = {}
    for i in range(l1):
        port = FlightList1[i]
        if FlightD[port][4] in startports1:
            startports1[FlightD[port][4]].append(i)
        else:
            startports1[FlightD[port][4]] = [i]
    res = []
    for j in range(l2):
        port = FlightD[FlightList2[j]][4]
        if port in startports1:
            for i in startports1[port]:
                res.append([i, j])
    return res

#当航班列表中有不满足飞机-航线限制时，返回True
def IsAirLimit(airplaneId, FlightList, FlightD, AirplaneLimit):
    for flight in FlightList:
        if (FlightD[flight][4], FlightD[flight][5], airplaneId) in AirplaneLimit:
            return True
    return False

#0代表起飞，1代表降落
def IsTimeSameRange(time1, time2, mode, Scene):
    if time1 >= Scene.ix[0][1] and time2 >= Scene.ix[0][1]:
        return True
    if time1 <= Scene.ix[1][0] and time2 <= Scene.ix[1][0]:
        return True
    return False

#判断一个航班串延迟一段时间是否可以运行
def GetNewDelayD(delaytime, FlightList1, delayD, FlightD, AirportCloseD, Scene):
    delayDcopy = delayD.copy()
    if delaytime <= datetime.timedelta(minutes = 0):
        return delayDcopy
    delaytimecopy = delaytime
    l = len(FlightList1)
    for i in range(l):
        delayDcopy[FlightList1[i]] = delayDcopy.get(FlightList1[i], datetime.timedelta(minutes = 0)) + delaytimecopy
        delaytimecopy = delayDcopy[FlightList1[i]]
        starttime = FlightD[FlightList1[i]][2] + delaytimecopy
        endtime = FlightD[FlightList1[i]][3] + delaytimecopy
        if i != l - 1:
            delaytimecopy = max(datetime.timedelta(minutes = 0), delaytimecopy - max(datetime.timedelta(minutes = 0), FlightD[FlightList1[i + 1]][2] - FlightD[FlightList1[i]][3] - datetime.timedelta(minutes = 50)))
        if IsAirportClose(AirportCloseD, FlightD[FlightList1[i]][4], starttime) or IsAirportClose(AirportCloseD, FlightD[FlightList1[i]][5], endtime):
            return {}
        if FlightD[FlightList1[i]][5] in (49, 50, 61) and endtime > Scene.ix[0][0] and endtime < Scene.ix[0][1]:
            return {}
    return delayDcopy



#GRASP算法的一次操作
def GRASPOnce(FlightExecuteList, FlightDismissList, initialCost, delayD, FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD):
    DownRCL = []
    UpRCL = []
    minTime = datetime.datetime(2000, 1, 1, 1, 1)
    maxTime = datetime.datetime(2100, 1, 1, 1, 1)
    Down_index = 0
    Up_index = 0

    if DownEnable == 1:
        #EFandDF
        # EFindexlist = [i for i in range(len(FlightExecuteList))]
        # while (EFindexlist and Down_index == 0):
        #     i_index = random.randint(0, len(EFindexlist) - 1)
        #     i = EFindexlist[i_index]
        #     EFindexlist.remove(i)
        for i in range(len(FlightExecuteList)):

            ef = FlightExecuteList[i]
            lef = len(ef[1])
            eflightcycle = findFlightCycle(FlightD, ef[1])


            #判断ef的延迟是否可减少
            NewdelayD = delayD.copy()
            for j in range(1, lef):
                f = ef[1][j]
                frontf = ef[1][j - 1]
                delaytime = FlightD[f][2] + NewdelayD.get(f, datetime.timedelta(minutes = 0)) - (FlightD[frontf][3] + NewdelayD.get(frontf, datetime.timedelta(minutes = 0))) - datetime.timedelta(minutes = 50)
                if delaytime <= datetime.timedelta(minutes = 0):
                    continue
                if NewdelayD.get(f, datetime.timedelta(minutes = 0)) == datetime.timedelta(minutes = 0):
                    continue
                time = max(delayDcompare.get(f, datetime.timedelta(minutes = 0)), max(datetime.timedelta(minutes = 0), NewdelayD.get(f, datetime.timedelta(minutes = 0)) - delaytime))
                if IsAirportClose(AirportCloseD, FlightD[f][4], time + FlightD[f][2]) or IsAirportClose(AirportCloseD, FlightD[f][5], time + FlightD[f][3]):
                    continue
                NewdelayD[f] = time
            newsubcost = 0
            for j in range(1, lef):
                f = ef[1][j]
                newsubcost += FlightD[f][6] * 100 * ((delayD.get(f, datetime.timedelta(minutes = 0)) - NewdelayD.get(f, datetime.timedelta(minutes = 0))) / datetime.timedelta(hours = 1))
            newcost = initialCost - newsubcost
            if newcost < initialCost:
                NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                NewFlightDismissList = copy.deepcopy(FlightDismissList)
                l = 0
                Down_index = 1
                DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])


            #当调整完以后
            if FlyDEnable == 1:
                for j in range(lef):
                    f_startport = FlightD[ef[1][j]][4]
                    #ef的一个航班串替换为FlyD的航班串
                    for k in range(j + 1, lef):
                        f_endport = FlightD[ef[1][k]][5]
                        solute = copy.deepcopy(FlyD.get((f_startport, f_endport, ef[0][1]), []))
                        for s in solute:
                            fset = []
                            for h in s:
                                fset = fset + FlightDismissList[h][1]
                            #若不满足时间限制(最多延迟x小时)
                            if j != 0:
                                delaytime = FlightD[ef[1][j - 1]][3] + delayD.get(ef[1][j - 1], datetime.timedelta(minutes = 0)) - (FlightD[fset[0]][2] + delayD.get(fset[0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50))
                                if delaytime > datetime.timedelta(hours = delayMaxhour):
                                    continue
                                NewdelayD = GetNewDelayD(delaytime, fset, delayD, FlightD, AirportCloseD, Scene)
                                if not NewdelayD:
                                    continue
                            else:
                                NewdelayD = delayD.copy()
                            #将ef推迟
                            if k != lef - 1:
                                efdelaytime = FlightD[fset[-1]][3] + NewdelayD.get(fset[-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50) - (FlightD[ef[1][k + 1]][2] + NewdelayD.get(ef[1][k + 1], datetime.timedelta(minutes = 0)))
                                if efdelaytime > datetime.timedelta(hours = delayMaxhour):
                                    continue
                                NewdelayD = GetNewDelayD(efdelaytime, ef[1][k + 1:], NewdelayD, FlightD, AirportCloseD, Scene)
                                if not NewdelayD:
                                    continue
                            #若不满足飞机-航线限制
                            if IsAirLimit(ef[0][0], fset, FlightD, AirplaneLimit):
                                continue
                            #若不满足联程航班限制
                            if j != 0 and (FlightD[ef[1][j]][1] != 0 and FlightD[ef[1][j]][1] == FlightD[ef[1][j - 1]][1]):
                                continue
                            if k != lef - 1 and (FlightD[ef[1][k + 1]][1] != 0 and FlightD[ef[1][k + 1]][1] == FlightD[ef[1][k]][1]):
                                continue
                            #若不满足中间台风机场不能停机限制
                            if FlightD[ef[1][j]][4] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][j]][2] + NewdelayD.get(ef[1][j], datetime.timedelta(minutes = 0)), FlightD[fset[0]][2] + NewdelayD.get(fset[0], datetime.timedelta(minutes = 0)), 0, Scene):
                                continue
                            if FlightD[ef[1][k]][5] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][k]][3] + NewdelayD.get(ef[1][k], datetime.timedelta(minutes = 0)), FlightD[fset[-1]][3] + NewdelayD.get(fset[-1], datetime.timedelta(minutes = 0)), 1, Scene):
                                continue
                            #计算成本
                            newsubcost = 0
                            for f in fset:
                                if FlightD[f][7] == ef[0][1]:
                                    newsubcost += FlightD[f][6] * 1000
                                newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            for f in ef[1][j: k + 1]:
                                if FlightD[f][7] == ef[0][1]:
                                    newsubcost -= FlightD[f][6] * 1000
                                newsubcost += FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            for f in ef[1][k + 1:]:
                                newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0) - delayD.get(f, datetime.timedelta(minutes = 0))) / datetime.timedelta(hours = 1))
                            newcost = initialCost - newsubcost
                            if newcost < initialCost:
                                #构造新解
                                NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                                NewFlightDismissList = copy.deepcopy(FlightDismissList)
                                newef = ef[1].copy()

                                newef = ef[1][:j] + fset + ef[1][k + 1:]
                                for h in s:
                                    NewFlightDismissList[h][1] = []

                                NewFlightExecuteList[i][1] = newef
                                #把ef[1][j]放入df中
                                eftmp = ef[1][j: k + 1]
                                if j != 0 and (FlightD[ef[1][j]][1] != 0 and FlightD[ef[1][j]][1] == FlightD[ef[1][j - 1]][1]):
                                    eftmp = eftmp[1:]
                                if k != lef - 1 and (FlightD[ef[1][k + 1]][1] != 0 and FlightD[ef[1][k + 1]][1] == FlightD[ef[1][k]][1]):
                                    eftmp = eftmp[:-1]
                                NewFlightDismissList.append([[ef[0][0], ef[0][1], 0, 0], eftmp])
                                l = len(newef) - len(ef[1])
                                DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])


                    #航班环插入中间及尾部
                    f_endport = FlightD[ef[1][j]][5]
                    solute = copy.deepcopy(FlyD.get((f_endport, f_endport, ef[0][1]), []))
                    for s in solute:
                        fset = []
                        for k in s:
                            fset = fset + FlightDismissList[k][1]
                        #若不满足时间限制
                        delaytime = FlightD[ef[1][j]][3] + delayD.get(ef[1][j], datetime.timedelta(minutes = 0)) - (FlightD[fset[0]][2] + delayD.get(fset[0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50))
                        if delaytime > datetime.timedelta(hours = delayMaxhour):
                            continue
                        NewdelayD = GetNewDelayD(delaytime, fset, delayD, FlightD, AirportCloseD, Scene)
                        if not NewdelayD:
                            continue
                        if j != lef - 1:
                            efdelaytime = FlightD[fset[-1]][3] + NewdelayD.get(fset[-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50) - (FlightD[ef[1][j + 1]][2] + NewdelayD.get(ef[1][j + 1], datetime.timedelta(minutes = 0)))
                            if efdelaytime > datetime.timedelta(hours = delayMaxhour):
                                continue
                            NewdelayD = GetNewDelayD(efdelaytime, ef[1][j + 1:], NewdelayD, FlightD, AirportCloseD, Scene)
                            if not NewdelayD:
                                continue
                        #若不满足飞机-航线限制
                        if IsAirLimit(ef[0][0], fset, FlightD, AirplaneLimit):
                            continue
                        #若不满足联程航班限制
                        if j != lef - 1 and (FlightD[ef[1][j]][1] != 0 and FlightD[ef[1][j + 1]][1] == FlightD[ef[1][j]][1]):
                            continue
                        #若不满足中间台风机场不能停机限制
                        if FlightD[ef[1][j]][5] in (49, 50, 61) and (not IsTimeSameRange(FlightD[ef[1][j]][3] + NewdelayD.get(ef[1][j], datetime.timedelta(minutes = 0)) , FlightD[fset[0]][2] + NewdelayD.get(fset[0], datetime.timedelta(minutes = 0)), 0, Scene)) and (not IsTimeSameRange(FlightD[ef[1][j]][3] + NewdelayD.get(ef[1][j], datetime.timedelta(minutes = 0)), FlightD[fset[-1]][3] + NewdelayD.get(fset[-1], datetime.timedelta(minutes = 0)), 0, Scene)):
                            continue
                        #计算成本
                        newsubcost = 0
                        for f in fset:
                            if FlightD[f][7] == ef[0][1]:
                                newsubcost += FlightD[f][6] * 1000
                            newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                        for f in ef[1][j + 1:]:
                            newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0) - delayD.get(f, datetime.timedelta(minutes = 0))) / datetime.timedelta(hours = 1))
                        newcost = initialCost - newsubcost
                        if newcost < initialCost:
                            #构造新解
                            NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                            NewFlightDismissList = copy.deepcopy(FlightDismissList)
                            newef = ef[1].copy()
                            newef = ef[1][:j + 1] + fset + ef[1][j + 1:]
                            for k in s:
                                NewFlightDismissList[k][1] = []

                            NewFlightExecuteList[i][1] = newef

                            Down_index = 1
                            l = len(newef) - len(ef[1])
                            DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])


                    # 换尾串
                    # 节省运算时间
                    # if j <= lef - 5:
                    #     continue
                    if j != 0:
                        efendport = FlightD[ef[1][j - 1]][5]
                    else:
                        efendport = ef[0][2]
                    for k in range(1, 80):
                        solute = copy.deepcopy(FlyD.get((efendport, k, ef[0][1]), []))
                        for s in solute:
                            fset = []
                            for h in s:
                                fset = fset + FlightDismissList[h][1]
                            #若不满足时间限制
                            if j != 0:
                                delaytime = FlightD[ef[1][j - 1]][3] + delayD.get(ef[1][j - 1], datetime.timedelta(minutes = 0)) - (FlightD[fset[0]][2] + delayD.get(fset[0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50))
                                if delaytime > datetime.timedelta(hours = delayMaxhour):
                                    continue
                                NewdelayD = GetNewDelayD(delaytime, fset, delayD, FlightD, AirportCloseD, Scene)
                                if not NewdelayD:
                                    continue
                            else:
                                NewdelayD = delayD.copy()
                            #若不满足飞机-航线限制
                            if IsAirLimit(ef[0][0], fset, FlightD, AirplaneLimit):
                                continue
                            #若不满足中间台风机场不能停机限制
                            if FlightD[ef[1][j]][4] in (49, 50, 61) and (not IsTimeSameRange(FlightD[ef[1][j]][2] + NewdelayD.get(ef[1][j], datetime.timedelta(minutes = 0)), FlightD[fset[0]][2] + NewdelayD.get(fset[0], datetime.timedelta(minutes = 0)), 1, Scene)):
                                continue
                            #联程航班限制
                            if j != 0 and (FlightD[ef[1][j]][1] != 0 and FlightD[ef[1][j]][1] == FlightD[ef[1][j - 1]][1]):
                                continue
                            #先计算成本再构建新解
                            #计算成本
                            newsubcost = 0
                            for f in fset:
                                if FlightD[f][7] == ef[0][1]:
                                    newsubcost += FlightD[f][6] * 1000
                                newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            for f in ef[1][j:]:
                                if FlightD[f][7] == ef[0][1]:
                                    newsubcost -= FlightD[f][6] * 1000
                                newsubcost += FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            if ef[0][3] == 1:
                                newsubcost -= 5000
                            if FlightDismissList[s[-1]][0][2] == 1:
                                newsubcost += 5000
                            newcost = initialCost - newsubcost
                            if newcost < initialCost:
                                NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                                NewFlightDismissList = copy.deepcopy(FlightDismissList)
                                newef = ef[1].copy()

                                newef = ef[1][:j] + fset

                                for k in s:
                                    NewFlightDismissList[k][1] = []
                                #判断联程航班来确定放入DF中的航班串
                                if j != 0 and (FlightD[ef[1][j]][1] != 0 and FlightD[ef[1][j]][1] == FlightD[ef[1][j - 1]][1]):
                                    NewFlightDismissList.append([[ef[0][0], ef[0][1], ef[0][3], FlightD[ef[1][-1]][5]], ef[1][j + 1:]])
                                else:
                                    NewFlightDismissList.append([[ef[0][0], ef[0][1], ef[0][3], FlightD[ef[1][-1]][5]], ef[1][j:]])
                                
                                NewFlightExecuteList[i][1] = newef
                                #将是否为尾航班标志互换
                                NewFlightExecuteList[i][0][3] = FlightDismissList[s[-1]][0][2]
                                NewFlightDismissList[s[-1]][0][2] = 0
                                Down_index = 1
                                l = len(newef) - len(ef[1])
                                DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])


                #尾航班串插入
                if ef[0][3] == 0:
                    if lef > 0:
                        efendtime = FlightD[ef[1][-1]][3] + delayD.get(ef[1][-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50)
                        efendport = FlightD[ef[1][-1]][5]
                    else:
                        efendtime = minTime
                        efendport = ef[0][2]
                    for k in range(1, 80):
                        solute = copy.deepcopy(FlyD.get((efendport, k, ef[0][1]), []))
                        for s in solute:
                            fset = []
                            for h in s:
                                fset = fset + FlightDismissList[h][1]
                            #若不满足时间限制
                            if lef != 0:
                                delaytime = FlightD[ef[1][-1]][3] + delayD.get(ef[1][-1], datetime.timedelta(minutes = 0)) - (FlightD[fset[0]][2] + delayD.get(fset[0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50))
                                if delaytime > datetime.timedelta(hours = delayMaxhour):
                                    continue
                                NewdelayD = GetNewDelayD(delaytime, fset, delayD, FlightD, AirportCloseD, Scene)
                                if not NewdelayD:
                                    continue
                            else:
                                NewdelayD = delayD.copy()
                            #若不满足飞机-航线限制
                            if IsAirLimit(ef[0][0], fset, FlightD, AirplaneLimit):
                                continue
                            #若不满足联程航班限制,因为插入尾部，所以肯定满足
                            #若不满足中间台风机场不能停机限制
                            if lef != 0 and FlightD[ef[1][-1]][5] in (49, 50, 61) and (not IsTimeSameRange(FlightD[ef[1][-1]][3] + NewdelayD.get(ef[1][-1], datetime.timedelta(minutes = 0)), FlightD[fset[0]][2] + NewdelayD.get(fset[0], datetime.timedelta(minutes = 0)), 0, Scene)):
                                continue
                            #计算成本
                            newsubcost = 0
                            for f in fset:
                                if FlightD[f][7] == ef[0][1]:
                                    newsubcost += FlightD[f][6] * 1000
                                newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            if FlightDismissList[s[-1]][0][2] == 1:
                                newsubcost += 5000
                            newcost = initialCost - newsubcost   
                            if newcost < initialCost:
                                #构造新解
                                NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                                NewFlightDismissList = copy.deepcopy(FlightDismissList)

                                newef = ef[1][:] + fset
                                for h in s:
                                    NewFlightDismissList[h][1] = []
                                NewFlightExecuteList[i][1] = newef
                                if FlightDismissList[s[-1]][0][2] == 1:
                                    NewFlightDismissList[s[-1]][0][2] = 0
                                    NewFlightExecuteList[i][0][3] = 1

                                Down_index = 1
                                l = len(newef) - len(ef[1])
                                DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])



            else:
                # DFindexlist = [j for j in range(len(FlightDismissList))]
                # while (DFindexlist and Down_index == 0):
                #     j_index = random.randint(0, len(DFindexlist) - 1)
                #     j = DFindexlist[j_index]
                #     DFindexlist.remove(j)
                for j in range(len(FlightDismissList)):

                    df = FlightDismissList[j]
                    ldf = len(df[1])
                    if not df:
                        continue
                    if ef[0][1] != df[0][1]:
                        continue
                    else:
                        #检测df中的子航班环，将环插入到合适的位置
                        dflightcycle = findFlightCycle(FlightD, df[1])
                        for flightcycle in dflightcycle:
                            if ((FlightD[flightcycle[0]][1] != 0 and FlightD[flightcycle[1]][1] != FlightD[flightcycle[0]][1]) or (FlightD[flightcycle[-1]][1] != 0 and FlightD[flightcycle[-2]][1] != FlightD[flightcycle[-1]][1])):
                                continue
                            flightcycle_starttime = FlightD[flightcycle[0]][2] + delayD.get(flightcycle[0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50)
                            flightcycle_endtime = FlightD[flightcycle[-1]][3] + delayD.get(flightcycle[-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50)
                            flightcycle_startport = FlightD[flightcycle[0]][4]
                            for k in range(-1, lef):
                                #判断机场是否相同
                                if k == -1:
                                    if ef[0][2] != flightcycle_startport:
                                        continue
                                else:
                                    if FlightD[ef[1][k]][5] != flightcycle_startport:
                                        continue
                                #判断时间是否可行
                                if k == -1:
                                    if ef[1] and FlightD[ef[1][0]][2] + delayD.get(ef[1][0], datetime.timedelta(minutes = 0)) < flightcycle_endtime:
                                        continue
                                    NewdelayD = delayD.copy()
                                else:
                                    delaytime = (FlightD[ef[1][k]][3] + delayD.get(ef[1][k], datetime.timedelta(minutes = 0))) - flightcycle_starttime
                                    if delaytime > datetime.timedelta(hours = delayMaxhour):
                                        continue
                                    NewdelayD = GetNewDelayD(delaytime, flightcycle, delayD, FlightD, AirportCloseD, Scene)
                                    if not NewdelayD:
                                        continue
                                    if k != lef - 1:
                                        efdelaytime = FlightD[flightcycle[-1]][3] + NewdelayD.get(flightcycle[-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50) - (FlightD[ef[1][k + 1]][2] + NewdelayD.get(ef[1][k + 1], datetime.timedelta(minutes = 0)))
                                        if efdelaytime > datetime.timedelta(hours = delayMaxhour):
                                            continue
                                        NewdelayD = GetNewDelayD(efdelaytime, ef[1][k + 1:], NewdelayD, FlightD, AirportCloseD, Scene)
                                        if not NewdelayD:
                                            continue
                                #判断插入的地方联程航班是否取消
                                if k != -1 and k != lef - 1 and (FlightD[ef[1][k]][1] != 0 and FlightD[ef[1][k + 1]][1] == FlightD[ef[1][k]][1]):
                                    continue
                                #判断是否飞机-航线限制
                                if IsAirLimit(ef[0][0], flightcycle, FlightD, AirplaneLimit):
                                    continue
                                #判断台风停机问题
                                if k == -1:
                                    if ef[1] and flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][0]][2] + NewdelayD.get(ef[1][0], datetime.timedelta(minutes = 0)), FlightD[flightcycle[-1]][3] + NewdelayD.get(flightcycle[-1], datetime.timedelta(minutes = 0)), 1, Scene):
                                        continue
                                elif k == lef - 1:
                                    if flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][-1]][3] + NewdelayD.get(ef[1][-1], datetime.timedelta(minutes = 0)), FlightD[flightcycle[0]][2] + NewdelayD.get(flightcycle[0], datetime.timedelta(minutes = 0)), 1, Scene):
                                        continue
                                else:
                                    if flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][k]][3] + NewdelayD.get(ef[1][k], datetime.timedelta(minutes = 0)), FlightD[flightcycle[0]][2] + NewdelayD.get(flightcycle[0], datetime.timedelta(minutes = 0)), 0, Scene):
                                        continue
                                    if flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][k + 1]][2] + NewdelayD.get(ef[1][k + 1], datetime.timedelta(minutes = 0)), FlightD[flightcycle[-1]][3] + NewdelayD.get(flightcycle[-1], datetime.timedelta(minutes = 0)), 0, Scene):
                                        continue
                                newsubcost = 0
                                for f in flightcycle:
                                    newsubcost += FlightD[f][6] * 1000
                                    newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                                for f in ef[1][k + 1:]:
                                    newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0) - delayD.get(f, datetime.timedelta(minutes = 0))) / datetime.timedelta(hours = 1))

                                newcost = initialCost - newsubcost
                                if newcost < initialCost:
                                    #构造新解
                                    NewFlightExecuteList = copy.deepcopy(FlightExecuteList) 
                                    NewFlightDismissList = copy.deepcopy(FlightDismissList)
                                    newef = ef[1].copy()
                                    newef = newef[:k + 1] + flightcycle + newef[k + 1:]
                                    newdf = df[1].copy()
                                    for f in flightcycle:
                                        newdf.remove(f)
                                    NewFlightExecuteList[i][1] = newef
                                    NewFlightDismissList[j][1] = newdf
                                    #费用肯定下降，所以加入到DownRcl
                                    Down_index = 1
                                    l = len(newef) - len(ef[1])
                                    DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])


                        #当ef没有尾串时，将df的尾航班串插入到ef的尾部
                        if ef[0][3] == 0:
                            efnum = lef - 1 - num
                            if lef > num:
                                efendtime = FlightD[ef[1][efnum]][3] + delayD.get(ef[1][efnum], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50)
                                efendport = FlightD[ef[1][efnum]][5]
                            else:
                                efendtime = minTime
                                efendport = ef[0][2]
                            for k in range(len(df[1])):
                                #如果起始机场为ef终止机场，且时间小于ef的endtime
                                if FlightD[df[1][k]][4] != efendport:
                                    continue
                                delaytime = efendtime - (FlightD[df[1][k]][2] + delayD.get(df[1][k], datetime.timedelta(minutes = 0)))
                                if delaytime > datetime.timedelta(hours = delayMaxhour):
                                    continue
                                NewdelayD = GetNewDelayD(delaytime, df[1][k:], delayD, FlightD, AirportCloseD, Scene)
                                if not NewdelayD:
                                    continue
                                    #台风场景限制
                                if efendport in (49, 50, 61) and not IsTimeSameRange(efendtime, FlightD[df[1][k]][2] + NewdelayD.get(df[1][k], datetime.timedelta(minutes = 0)), 0, Scene):
                                    continue
                                #ef的联程航班没有被拆除
                                if not (lef <= num or lef < 2 or num == 0 or not (FlightD[ef[1][efnum]][1] != 0 and FlightD[ef[1][efnum + 1]][1] == FlightD[ef[1][efnum]][1])):
                                    continue
                                if not (k == 0 or not (FlightD[df[1][k]][1] != 0 and FlightD[df[1][k - 1]][1] == FlightD[df[1][k]][1])):
                                    continue
                                #航线限制
                                if not IsAirLimit(ef[0][0], df[1][k:], FlightD, AirplaneLimit):
                                    #计算成本
                                    newsubcost = 0
                                    for f in df[1][k:]:
                                        newsubcost += FlightD[f][6] * 1000
                                        newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                                    if efnum < 0:
                                        for f in ef[1]:
                                            newsubcost -= FlightD[f][6] * 1000
                                            newsubcost += FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                                    else:
                                        for f in ef[1][efnum + 1:]:
                                            newsubcost -= FlightD[f][6] * 1000
                                            newsubcost += FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                                    newcost = initialCost - newsubcost if df[0][2] == 0 else initialCost - newsubcost - 5000
                                    if newcost < initialCost:
                                        #构建新解
                                        NewFlightExecuteList = copy.deepcopy(FlightExecuteList) 
                                        NewFlightDismissList = copy.deepcopy(FlightDismissList)
                                        newef = ef[1].copy()
                                        if efnum < 0:
                                            newef = df[1][k:]
                                        else:
                                            newef = newef[:efnum + 1] + df[1][k:]
                                        #若df不是联程航班切断
                                        if k == 0 or not (FlightD[df[1][k]][1] != 0 and FlightD[df[1][k - 1]][1] == FlightD[df[1][k]][1]):
                                            newdf = df[1][:k].copy()
                                        else:
                                            newdf = df[1][:k - 1].copy()
                                        NewFlightExecuteList[i][1] = newef
                                        NewFlightDismissList[j][1] = newdf
                                        tmp = NewFlightExecuteList[i][0][3]
                                        NewFlightExecuteList[i][0][3] = df[0][2]
                                        NewFlightDismissList[j][0][2] = tmp
                                        #若ef不是联程航班切断
                                        if efnum >= 0:
                                            if lef <= num or lef < 2 or num == 0 or not (FlightD[ef[1][efnum]][1] != 0 and FlightD[ef[1][efnum + 1]][1] == FlightD[ef[1][efnum]][1]):
                                                NewFlightDismissList.append([[ef[0][0], ef[0][1], 0, 0], ef[1][efnum + 1:]])
                                            else:
                                                NewFlightDismissList.append([[ef[0][0], ef[0][1], 0, 0], ef[1][efnum + 2:]])

                                        Down_index = 1
                                        l = len(newef) - len(ef[1])
                                        DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])
                        

                        #ef与df互换尾串操作(不管df联程或者时间是否满足)
                        samestartstring = findSameStartport(FlightD, ef[1], df[1])
                        for string in samestartstring:
                            efstartindex = string[0]
                            dfstartindex = string[1]
                            #若不满足时间限制
                            if efstartindex != 0:
                                delaytime = FlightD[ef[1][efstartindex - 1]][3] + delayD.get(ef[1][efstartindex - 1], datetime.timedelta(minutes = 0)) - (FlightD[df[1][dfstartindex]][2] + delayD.get(df[1][dfstartindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50))
                                if delaytime > datetime.timedelta(hours = delayMaxhour):
                                    continue
                                NewdelayD = GetNewDelayD(delaytime, df[1][dfstartindex:], delayD, FlightD, AirportCloseD, Scene)
                                if not NewdelayD:
                                    continue
                            else:
                                NewdelayD = delayD.copy()
                            # if dfstartindex != 0 and FlightD[df[1][dfstartindex - 1]][3] > FlightD[ef[1][efstartindex]][2] - datetime.timedelta(minutes = 50):
                            #     continue
                            #若不满足飞机-航线限制
                            if IsAirLimit(ef[0][0], df[1][dfstartindex:], FlightD, AirplaneLimit):
                                continue
                            #若不满足联程航班限制
                            if efstartindex != 0 and (FlightD[ef[1][efstartindex]][1] != 0 and FlightD[ef[1][efstartindex]][1] == FlightD[ef[1][efstartindex - 1]][1]):
                                continue
                            if dfstartindex != 0 and (FlightD[df[1][dfstartindex]][1] != 0 and FlightD[df[1][dfstartindex]][1] == FlightD[df[1][dfstartindex - 1]][1]):
                                continue
                            #若不满足中间台风机场不能停机限制
                            if FlightD[ef[1][efstartindex]][4] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efstartindex]][2] + NewdelayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)), FlightD[df[1][dfstartindex]][2] + NewdelayD.get(df[1][dfstartindex], datetime.timedelta(minutes = 0)), 0, Scene):
                                continue
                            #计算成本
                            newsubcost = 0
                            for f in df[1][dfstartindex:]:
                                newsubcost += FlightD[f][6] * 1000
                                newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            for f in ef[1][efstartindex:]:
                                newsubcost -= FlightD[f][6] * 1000
                                newsubcost += FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            if ef[0][3] == 1:
                                newsubcost -= 5000
                            if df[0][2] == 1:
                                newsubcost += 5000
                            newcost = initialCost - newsubcost

                            if newcost < initialCost:
                                #构造新解
                                NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                                NewFlightDismissList = copy.deepcopy(FlightDismissList)
                                newef = ef[1].copy()
                                newdf = df[1].copy()

                                newef = ef[1][:efstartindex] + df[1][dfstartindex:]
                                if dfstartindex != 0 and (FlightD[df[1][dfstartindex]][1] != 0 and FlightD[df[1][dfstartindex]][1] == FlightD[df[1][dfstartindex - 1]][1]):
                                    newdf = df[1][:dfstartindex - 1]
                                else:
                                    newdf = df[1][:dfstartindex]
                                
                                NewFlightExecuteList[i][1] = newef
                                NewFlightDismissList[j][1] = newdf
                                #将是否为尾航班标志互换
                                NewFlightExecuteList[i][0][3] = df[0][2]
                                NewFlightDismissList[j][0][2] = 0
                                #df的最终截止机场也需要改变
                                NewFlightDismissList.append([[ef[0][0], ef[0][1], ef[0][3], FlightD[ef[1][-1]][5]], ef[1][efstartindex:]])
                                Down_index = 1
                                l = len(newef) - len(ef[1])
                                DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])


                        #ef与df首尾相同的串互换
                        samestring = findSameStartEnd(FlightD, ef[1], df[1])
                        for string in samestring:
                            efstartindex = string[0][0]
                            efendindex = string[0][1]
                            dfstartindex = string[1][0]
                            dfendindex = string[1][1]
                            #若不满足时间限制
                            if efstartindex != 0 and FlightD[ef[1][efstartindex - 1]][3] + delayD.get(ef[1][efstartindex - 1], datetime.timedelta(minutes = 0)) > FlightD[df[1][dfstartindex]][2] + delayD.get(df[1][dfstartindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50):
                                continue
                            if dfstartindex != 0 and FlightD[df[1][dfstartindex - 1]][3] + delayD.get(df[1][dfstartindex - 1], datetime.timedelta(minutes = 0)) > FlightD[ef[1][efstartindex]][2] + delayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50):
                                continue
                            if efendindex != lef and FlightD[ef[1][efendindex]][2] + delayD.get(ef[1][efendindex], datetime.timedelta(minutes = 0)) < FlightD[df[1][dfendindex - 1]][3] + delayD.get(df[1][dfendindex - 1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50):
                                continue
                            if dfendindex != ldf and FlightD[df[1][dfendindex]][2] + delayD.get(df[1][dfendindex], datetime.timedelta(minutes = 0)) < FlightD[ef[1][efendindex - 1]][3] + delayD.get(ef[1][efendindex - 1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50):
                                continue

                            #若不满足飞机-航线限制
                            if IsAirLimit(ef[0][0], df[1][dfstartindex: dfendindex], FlightD, AirplaneLimit):
                                continue
                            #若不满足联程航班限制
                            if efstartindex != 0 and (FlightD[ef[1][efstartindex]][1] != 0 and FlightD[ef[1][efstartindex]][1] == FlightD[ef[1][efstartindex - 1]][1]):
                                continue
                            if efendindex != lef and (FlightD[ef[1][efendindex]][1] != 0 and FlightD[ef[1][efendindex]][1] == FlightD[ef[1][efendindex - 1]][1]):
                                continue
                            if dfstartindex != 0 and (FlightD[df[1][dfstartindex]][1] != 0 and FlightD[df[1][dfstartindex]][1] == FlightD[df[1][dfstartindex - 1]][1]):
                                continue
                            if dfendindex != ldf and (FlightD[df[1][dfendindex]][1] != 0 and FlightD[df[1][dfendindex]][1] == FlightD[df[1][dfendindex - 1]][1]):
                                continue
                            #若不满足中间台风机场不能停机限制
                            if FlightD[ef[1][efstartindex]][4] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efstartindex]][2] + delayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)), FlightD[df[1][dfstartindex]][2] + delayD.get(df[1][dfstartindex], datetime.timedelta(minutes = 0)), 0, Scene):
                                continue
                            if FlightD[ef[1][efendindex - 1]][5] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efendindex - 1]][3] + delayD.get(ef[1][efendindex - 1], datetime.timedelta(minutes = 0)), FlightD[df[1][dfendindex - 1]][3] + delayD.get(df[1][dfendindex - 1], datetime.timedelta(minutes = 0)), 1, Scene):
                                continue

                            #计算成本
                            newsubcost = 0
                            for f in df[1][dfstartindex: dfendindex]:
                                newsubcost += FlightD[f][6] * 1000
                                newsubcost -= FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            for f in ef[1][efstartindex: efendindex]:
                                newsubcost -= FlightD[f][6] * 1000
                                newsubcost += FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))

                            newcost = initialCost - newsubcost
                            if newcost < initialCost:
                                #构造新解
                                NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                                NewFlightDismissList = copy.deepcopy(FlightDismissList)
                                newef = ef[1].copy()
                                newdf = df[1].copy()

                                newef = ef[1][:efstartindex] + df[1][dfstartindex: dfendindex] + ef[1][efendindex:]
                                newdf = df[1][:dfstartindex] + ef[1][efstartindex: efendindex] + df[1][dfendindex:]

                                NewFlightExecuteList[i][1] = newef
                                NewFlightDismissList[j][1] = newdf

                                Down_index = 1
                                l = len(newef) - len(ef[1])
                                DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, delayD, l])


                        # #ef与df首尾相同的串互换(不管df联程或者时间是否满足)
                        # samestring = findSameStartEnd(FlightD, ef[1], df[1])
                        # for string in samestring:
                        #     efstartindex = string[0][0]
                        #     efendindex = string[0][1]
                        #     dfstartindex = string[1][0]
                        #     dfendindex = string[1][1]
                        #     #若不满足时间限制
                        #     if efstartindex != 0:
                        #         dfdelaytime = (FlightD[ef[1][efstartindex - 1]][3] + delayD.get(ef[1][efstartindex - 1], datetime.timedelta(minutes = 0))) - (FlightD[df[1][dfstartindex]][2] + delayD.get(df[1][dfstartindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50))
                        #         if dfdelaytime > datetime.timedelta(hours = delayMaxhour):
                        #             continue
                        #         NewdelayD = GetNewDelayD(dfdelaytime, df[1][dfstartindex: dfendindex], delayD, FlightD, AirportCloseD, Scene)
                        #         if not NewdelayD:
                        #             continue
                        #     if efendindex != lef:
                        #         efdelaytime = FlightD[df[1][dfendindex - 1]][3] + NewdelayD.get(df[1][dfendindex - 1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50) - (FlightD[ef[1][efendindex]][2] + NewdelayD.get(ef[1][efendindex], datetime.timedelta(minutes = 0)))
                        #         if efdelaytime > datetime.timedelta(hours = delayMaxhour):
                        #             continue
                        #         NewdelayD = GetNewDelayD(efdelaytime, ef[1][efendindex:], NewdelayD, FlightD, AirportCloseD, Scene)
                        #         if not NewdelayD:
                        #             continue
                        #     #若不满足飞机-航线限制
                        #     if IsAirLimit(ef[0][0], df[1][dfstartindex: dfendindex], FlightD, AirplaneLimit):
                        #         continue
                        #     #若不满足联程航班限制
                        #     if efstartindex != 0 and (FlightD[ef[1][efstartindex]][1] != 0 and FlightD[ef[1][efstartindex]][1] == FlightD[ef[1][efstartindex - 1]][1]):
                        #         continue
                        #     if efendindex != lef and (FlightD[ef[1][efendindex]][1] != 0 and FlightD[ef[1][efendindex]][1] == FlightD[ef[1][efendindex - 1]][1]):
                        #         continue
                        #     #若不满足中间台风机场不能停机限制
                        #     if FlightD[ef[1][efstartindex]][4] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efstartindex]][2] + NewdelayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)), FlightD[df[1][dfstartindex]][2] + delayD.get(df[1][dfstartindex], datetime.timedelta(minutes = 0)), 0, Scene):
                        #         continue
                        #     if FlightD[ef[1][efendindex - 1]][5] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efendindex - 1]][3] + NewdelayD.get(ef[1][efendindex - 1], datetime.timedelta(minutes = 0)), FlightD[df[1][dfendindex - 1]][3] + delayD.get(df[1][dfendindex - 1], datetime.timedelta(minutes = 0)), 1, Scene):
                        #         continue

                        #     #计算成本
                        #     newsubcost = 0
                        #     for f in df[1][dfstartindex: dfendindex]:
                        #         newsubcost += FlightD[f][6] * 1000
                        #         newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                        #     for f in ef[1][efstartindex: efendindex]:
                        #         newsubcost -= FlightD[f][6] * 1000
                        #         newsubcost += FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                        #     for f in ef[1][efendindex:]:
                        #         newsubcost -= FlightD[f][6] * 100 * (NewdelayD.get(f, datetime.timedelta(minutes = 0) - delayD.get(f, datetime.timedelta(minutes = 0))) / datetime.timedelta(hours = 1))
                        #     newcost = initialCost - newsubcost
                        #     if newcost < initialCost:
                        #         #构造新解
                        #         NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                        #         NewFlightDismissList = copy.deepcopy(FlightDismissList)
                        #         newef = ef[1].copy()
                        #         newdf = df[1].copy()

                        #         newef = ef[1][:efstartindex] + df[1][dfstartindex: dfendindex] + ef[1][efendindex:]
                        #         if dfendindex != ldf and (FlightD[df[1][dfendindex]][1] != 0 and FlightD[df[1][dfendindex]][1] == FlightD[df[1][dfendindex - 1]][1]):
                        #             newdf = df[1][dfendindex + 1:]
                        #         else:
                        #             newdf = df[1][dfendindex:] 
                                
                        #         if dfstartindex != 0 and (FlightD[df[1][dfstartindex]][1] != 0 and FlightD[df[1][dfstartindex]][1] == FlightD[df[1][dfstartindex - 1]][1]):
                        #             NewFlightDismissList.append([[df[0][0], df[0][1], 0, 0], df[1][:dfstartindex - 1]])
                        #         else:
                        #             NewFlightDismissList.append([[df[0][0], df[0][1], 0, 0], df[1][:dfstartindex]])

                        #         NewFlightDismissList.append([[ef[0][0], ef[0][1], 0, 0], ef[1][efstartindex: efendindex]])
                        #         NewFlightExecuteList[i][1] = newef
                        #         NewFlightDismissList[j][1] = newdf

                        #         Down_index = 1
                        #         l = len(newef) - len(ef[1])
                        #         DownRCL.append([newcost, NewFlightExecuteList, NewFlightDismissList, NewdelayD, l])
                        

                    
    
    #EF and EF
    EFindexlist = [i for i in range(len(FlightExecuteList))]
    while (EFindexlist and Down_index == 0 and Up_index == 0):
        i_index = random.randint(0, len(EFindexlist) - 1)
        i = EFindexlist[i_index]
        EFindexlist.remove(i)

        #ef与ef的互换子航班环与尾航班串
        ef = FlightExecuteList[i]
        lef = len(ef[1])
        eflightcycle = findFlightCycle(FlightD, ef[1])
        EFindexlist2 = [j for j in range(i)]
        while (EFindexlist2 and Up_index == 0):
            j_index = random.randint(0, len(EFindexlist2) - 1)
            j = EFindexlist2[j_index]
            EFindexlist2.remove(j)

            ef2 = FlightExecuteList[j]
            lef2 = len(ef2[1])
            #当飞机类型不同时，不操作
            if ef[0][1] != ef2[0][1]:
                continue

            #互换首尾相同的串，这样就包括了航班环
            #ef与ef2首尾相同的串互换
            samestring = findSameStartEnd(FlightD, ef[1], ef2[1])
            for string in samestring:
                efstartindex = string[0][0]
                efendindex = string[0][1]
                ef2startindex = string[1][0]
                ef2endindex = string[1][1]
                #若不满足时间限制
                if efstartindex != 0 and FlightD[ef[1][efstartindex - 1]][3] + delayD.get(ef[1][efstartindex - 1], datetime.timedelta(minutes = 0)) > FlightD[ef2[1][ef2startindex]][2] + delayD.get(ef2[1][ef2startindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50):
                    continue
                if ef2startindex != 0 and FlightD[ef2[1][ef2startindex - 1]][3] + delayD.get(ef2[1][ef2startindex - 1], datetime.timedelta(minutes = 0)) > FlightD[ef[1][efstartindex]][2] + delayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50):
                    continue
                if efendindex != lef and FlightD[ef[1][efendindex]][2] + delayD.get(ef[1][efendindex], datetime.timedelta(minutes = 0)) < FlightD[ef2[1][ef2endindex - 1]][3] + delayD.get(ef2[1][ef2endindex - 1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50):
                    continue
                if ef2endindex != lef2 and FlightD[ef2[1][ef2endindex]][2] + delayD.get(ef2[1][ef2endindex], datetime.timedelta(minutes = 0)) < FlightD[ef[1][efendindex - 1]][3] + delayD.get(ef[1][efendindex - 1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50):
                    continue

                #若不满足飞机-航线限制
                if IsAirLimit(ef[0][0], ef2[1][ef2startindex: ef2endindex], FlightD, AirplaneLimit):
                    continue
                if IsAirLimit(ef2[0][0], ef[1][efstartindex: efendindex], FlightD, AirplaneLimit):
                    continue
                #若不满足联程航班限制
                if efstartindex != 0 and (FlightD[ef[1][efstartindex]][1] != 0 and FlightD[ef[1][efstartindex]][1] == FlightD[ef[1][efstartindex - 1]][1]):
                    continue
                if efendindex != lef and (FlightD[ef[1][efendindex]][1] != 0 and FlightD[ef[1][efendindex]][1] == FlightD[ef[1][efendindex - 1]][1]):
                    continue
                if ef2startindex != 0 and (FlightD[ef2[1][ef2startindex]][1] != 0 and FlightD[ef2[1][ef2startindex]][1] == FlightD[ef2[1][ef2startindex - 1]][1]):
                    continue
                if ef2endindex != lef2 and (FlightD[ef2[1][ef2endindex]][1] != 0 and FlightD[ef2[1][ef2endindex]][1] == FlightD[ef2[1][ef2endindex - 1]][1]):
                    continue
                #若不满足中间台风机场不能停机限制
                if FlightD[ef[1][efstartindex]][4] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efstartindex]][2] + delayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)), FlightD[ef2[1][ef2startindex]][2] + delayD.get(ef2[1][ef2startindex], datetime.timedelta(minutes = 0)), 0, Scene):
                    continue
                if FlightD[ef[1][efendindex - 1]][5] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efendindex - 1]][3] + delayD.get(ef[1][efendindex - 1], datetime.timedelta(minutes = 0)), FlightD[ef2[1][ef2endindex - 1]][3] + delayD.get(ef2[1][ef2endindex - 1], datetime.timedelta(minutes = 0)), 1, Scene):
                    continue
                #构造新解
                NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                NewFlightDismissList = copy.deepcopy(FlightDismissList)
                newef = ef[1].copy()
                newef2 = ef2[1].copy()

                newef = ef[1][:efstartindex] + ef2[1][ef2startindex: ef2endindex] + ef[1][efendindex:]
                newef2 = ef2[1][:ef2startindex] + ef[1][efstartindex: efendindex] + ef2[1][ef2endindex:]

                NewFlightExecuteList[i][1] = newef
                NewFlightExecuteList[j][1] = newef2

                #计算成本
                Up_index = 1
                UpRCL.append([initialCost, NewFlightExecuteList, NewFlightDismissList, delayD])


            #ef与ef2互换尾串操作
            samestartstring = findSameStartport(FlightD, ef[1], ef2[1])
            for string in samestartstring:
                efstartindex = string[0]
                ef2startindex = string[1]
                #若不满足时间限制
                if efstartindex != 0 and FlightD[ef[1][efstartindex - 1]][3] + delayD.get(ef[1][efstartindex - 1], datetime.timedelta(minutes = 0)) > FlightD[ef2[1][ef2startindex]][2] + delayD.get(ef2[1][ef2startindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50):
                    continue
                if ef2startindex != 0 and FlightD[ef2[1][ef2startindex - 1]][3] + delayD.get(ef2[1][ef2startindex - 1], datetime.timedelta(minutes = 0)) > FlightD[ef[1][efstartindex]][2] + delayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50):
                    continue
                #若不满足飞机-航线限制
                if IsAirLimit(ef[0][0], ef2[1][ef2startindex:], FlightD, AirplaneLimit):
                    continue
                if IsAirLimit(ef2[0][0], ef[1][efstartindex:], FlightD, AirplaneLimit):
                    continue
                #若不满足联程航班限制
                if efstartindex != 0 and (FlightD[ef[1][efstartindex]][1] != 0 and FlightD[ef[1][efstartindex]][1] == FlightD[ef[1][efstartindex - 1]][1]):
                    continue
                if ef2startindex != 0 and (FlightD[ef2[1][ef2startindex]][1] != 0 and FlightD[ef2[1][ef2startindex]][1] == FlightD[ef2[1][ef2startindex - 1]][1]):
                    continue
                #若不满足中间台风机场不能停机限制
                if FlightD[ef[1][efstartindex]][4] in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][efstartindex]][2] + delayD.get(ef[1][efstartindex], datetime.timedelta(minutes = 0)), FlightD[ef2[1][ef2startindex]][2] + delayD.get(ef2[1][ef2startindex], datetime.timedelta(minutes = 0)), 0, Scene):
                    continue
                #计算成本
                newsubcost = 0
                for f in ef2[1][ef2startindex:]:
                    newsubcost += FlightD[f][6] * 1000
                for f in ef[1][efstartindex:]:
                    newsubcost -= FlightD[f][6] * 1000
                if ef[0][3] == 1:
                    newsubcost -= 5000
                if ef2[0][2] == 1:
                    newsubcost += 5000
                newcost = initialCost - newsubcost

                if newcost < initialCost:
                    #构造新解
                    NewFlightExecuteList = copy.deepcopy(FlightExecuteList)
                    NewFlightDismissList = copy.deepcopy(FlightDismissList)
                    newef = ef[1].copy()
                    newef2 = ef2[1].copy()

                    newef = ef[1][:efstartindex] + ef2[1][ef2startindex:]
                    newef2 = ef2[1][:ef2startindex] + ef[1][efstartindex:]

                    NewFlightExecuteList[i][1] = newef
                    NewFlightExecuteList[j][1] = newef2
                    #将是否为尾航班标志互换
                    tmp = NewFlightExecuteList[i][0][3]
                    NewFlightExecuteList[i][0][3] = ef2[0][3]
                    NewFlightExecuteList[j][0][3] = tmp

                    Up_index = 1
                    UpRCL.append([initialCost, NewFlightExecuteList, NewFlightDismissList, delayD])

            #ef2的航班环插入到ef中
            ef2lightcycle = findFlightCycle(FlightD, ef2[1])
            for flightcycle in ef2lightcycle:
                if ((FlightD[flightcycle[0]][1] != 0 and FlightD[flightcycle[1]][1] != FlightD[flightcycle[0]][1]) or (FlightD[flightcycle[-1]][1] != 0 and FlightD[flightcycle[-2]][1] != FlightD[flightcycle[-1]][1])):
                    continue
                flightcycle_starttime = FlightD[flightcycle[0]][2] + delayD.get(flightcycle[0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50)
                flightcycle_endtime = FlightD[flightcycle[-1]][3] + delayD.get(flightcycle[-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50)
                flightcycle_startport = FlightD[flightcycle[0]][4]
                for k in range(-1, lef):
                    #判断机场是否相同
                    if k == -1:
                        if ef[0][2] != flightcycle_startport:
                            continue
                    else:
                        if FlightD[ef[1][k]][5] != flightcycle_startport:
                            continue
                    #判断时间是否可行
                    if k == -1:
                        if ef[1] and FlightD[ef[1][0]][2] + delayD.get(ef[1][0], datetime.timedelta(minutes = 0)) < flightcycle_endtime:
                            continue
                    elif k == lef - 1:
                        if flightcycle_starttime < FlightD[ef[1][-1]][3] + delayD.get(ef[1][-1], datetime.timedelta(minutes = 0)):
                            continue
                    else:
                        if FlightD[ef[1][k + 1]][2] + delayD.get(ef[1][k + 1], datetime.timedelta(minutes = 0)) < flightcycle_endtime or flightcycle_starttime < FlightD[ef[1][k]][3] + delayD.get(ef[1][k], datetime.timedelta(minutes = 0)):
                            continue
                    #判断插入的地方联程航班是否取消
                    if k != -1 and k != lef - 1 and (FlightD[ef[1][k]][1] != 0 and FlightD[ef[1][k + 1]][1] == FlightD[ef[1][k]][1]):
                        continue
                    #判断是否飞机-航线限制
                    if IsAirLimit(ef[0][0], flightcycle, FlightD, AirplaneLimit):
                        continue
                    #判断台风停机问题
                    if k == -1:
                        if ef[1] and flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][0]][2] + delayD.get(ef[1][0], datetime.timedelta(minutes = 0)), FlightD[flightcycle[-1]][3] + delayD.get(flightcycle[-1], datetime.timedelta(minutes = 0)), 1, Scene):
                            continue
                    elif k == lef - 1:
                        if flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][-1]][3] + delayD.get(ef[1][-1], datetime.timedelta(minutes = 0)), FlightD[flightcycle[0]][2] + delayD.get(flightcycle[0], datetime.timedelta(minutes = 0)), 1, Scene):
                            continue
                    else:
                        if flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][k]][3] + delayD.get(ef[1][k], datetime.timedelta(minutes = 0)), FlightD[flightcycle[0]][2] + delayD.get(flightcycle[0], datetime.timedelta(minutes = 0)), 0, Scene):
                            continue
                        if flightcycle_startport in (49, 50, 61) and not IsTimeSameRange(FlightD[ef[1][k + 1]][2] + delayD.get(ef[1][k + 1], datetime.timedelta(minutes = 0)), FlightD[flightcycle[-1]][3] + delayD.get(flightcycle[-1], datetime.timedelta(minutes = 0)), 0, Scene):
                            continue

                    #构造新解
                    NewFlightExecuteList = copy.deepcopy(FlightExecuteList) 
                    NewFlightDismissList = copy.deepcopy(FlightDismissList)
                    newef = ef[1].copy()
                    newef = newef[:k + 1] + flightcycle + newef[k + 1:]
                    newef2 = ef2[1].copy()
                    for f in flightcycle:
                        newef2.remove(f)
                    NewFlightExecuteList[i][1] = newef
                    NewFlightExecuteList[j][1] = newef2
                    Up_index = 1
                    UpRCL.append([initialCost, NewFlightExecuteList, NewFlightDismissList, delayD, 4])
    return DownRCL, UpRCL


#生成csv文件
def GetResult(Flight, minSolution, FlightD, delayD, DomesticJoint):
    FlightExecuteList = minSolution[0]
    FlightDismissList = minSolution[1]
    d = {}
    airlist = []
    l = 0
    for ef in FlightExecuteList:
        for f in ef[1]:
            d[f] = ef[0][0]
        airlist.append(ef[0][0])

    #先统计需要拉直的联程航班，只有在EF中的拉直联程航班需要写拉直
    straightset = set()
    for ef in FlightExecuteList:
        for f in ef[1]:
            if f <= 2364 and FlightD[f][10] == 1:
                l += 1
                straightset.add(f)
                straightset.add(DomesticJoint[f])

    iscancellist = []
    airplanidlist = []
    starttime = []
    endtime = []
    Flight['isStraight'] = 0
    for i in Flight.index:
        f = Flight['flightId'][i]
        if f in straightset:
            Flight['endAirport'][i] = FlightD[f][5]
            Flight['isStraight'][i] = 1
        if f in d:
            iscancellist.append(0)
            airplanidlist.append(d[Flight['flightId'][i]])
            if f in straightset:
                starttime.append(FlightD[f][2] + delayD.get(f, datetime.timedelta(minutes = 0)))
                endtime.append(FlightD[f][3] + delayD.get(f, datetime.timedelta(minutes = 0)))
            else:
                starttime.append(Flight['startDateTime'][i] + delayD.get(f, datetime.timedelta(minutes = 0)))
                endtime.append(Flight['endDateTime'][i] + delayD.get(f, datetime.timedelta(minutes = 0)))
        else:
            iscancellist.append(1)
            airplanidlist.append(Flight['airplaneId'][i])
            starttime.append(Flight['startDateTime'][i])
            endtime.append(Flight['endDateTime'][i])
    Flight['isCancel'] = iscancellist
    Flight['airplaneId'] = airplanidlist
    Flight['startDateTime'] = starttime
    Flight['endDateTime'] = endtime

    res = generateResult(Flight)
    res = res.sort_values('flightId')
    print("航班拉直数量：", l)
    res.to_csv('res.csv', index = False, header = False)
    return res

#求时间交集
def TimeInter(time1, time2):
    if time1[0] == None or time2[0] == None:
        return [None, None]
    minTime = max(time1[0], time2[0])
    maxTime = min(time1[1], time2[1])
    if minTime >= maxTime:
        return [None, None]
    return [minTime, maxTime]

#求时间差集
def TimeSub(time1list, time2):
    if not time1list:
        return []
    res = []
    for time1 in time1list:
        if time2[0] > time1[0] and time2[1] < time1[1]:
            res.append([time1[0], time2[0]])
            res.append([time2[1], time1[1]])
            continue
        tmp = TimeInter(time1, time2)
        if tmp[0] == None:
            tmp = [time1[1], time1[1]]
        res_tmp = time1.copy()
        if tmp[0] == time1[0]:
            res_tmp[0] = tmp[1]
        if tmp[1] == time1[1]:
            res_tmp[1] = tmp[0]
        if res_tmp[1] > res_tmp[0]:
            res.append(res_tmp)
    return res

#获得调机开始与结束时间，starttime为前一航班落地时间，endtime为后一航班开始时间
def GetFerryTime(starttime, endtime, airtype, startport, endport, AirportCloseD, FlytimeD, Scene):
    #当航班不在调机飞行时间表中时，返回None
    if not (airtype, startport, endport) in FlytimeD:
        return None, None

    flytime = datetime.timedelta(minutes = int(FlytimeD[(airtype, startport, endport)]))
    #分别为调机的起飞时间的区间上下界
    ferryMinstarttime = starttime + datetime.timedelta(minutes = 50)
    ferryMaxstarttime = endtime - flytime - datetime.timedelta(minutes = 50)
    #若中间时间不够调机使用,则返回None
    if ferryMinstarttime > ferryMaxstarttime:
        return None, None

    #InterList为所有可起飞时间区间
    minTime = datetime.datetime(2000, 1, 1, 1, 1)
    maxTime = datetime.datetime(2100, 1, 1, 1, 1)

    sceneportset = set(Scene['airport'])
    closeportset = set(AirportCloseD.keys())

    InitialTime = [[ferryMinstarttime, ferryMaxstarttime]]
    SubTimeSet = []
    #当调机结束机场在受台风影响机场时，等台风结束再到, 因为停机问题，所以出发机场在台风期间这种情况不存在
    if endport in sceneportset:
        SubTimeSet.append([minTime, Scene.ix[0][1] - flytime])
    if startport in sceneportset:
        SubTimeSet.append([Scene.ix[0][0], maxTime])
    #当出发机场在宵禁机场中时
    if startport in closeportset:
        endday = min(AirportCloseD[startport][0][3], ferryMaxstarttime.date())
        beginday = ferryMinstarttime.date()
        while(beginday <= endday):
            for time in AirportCloseD[startport]:
                beginCloseTime = datetime.datetime(beginday.year, beginday.month, beginday.day, time[0].hour, time[0].minute)
                endCloseTime = datetime.datetime(beginday.year, beginday.month, beginday.day, time[1].hour, time[1].minute)
                SubTimeSet.append([beginCloseTime, endCloseTime])
            beginday = beginday + datetime.timedelta(days = 1)
    #当结束机场在宵禁机场时
    if endport in closeportset:
        endMaxtime = endtime - datetime.timedelta(minutes = 50)
        endday = min(AirportCloseD[endport][0][3], endMaxtime.date())
        beginday = ferryMinstarttime.date()
        while(beginday <= endday):
            for time in AirportCloseD[endport]:
                beginCloseTime = datetime.datetime(beginday.year, beginday.month, beginday.day, time[0].hour, time[0].minute)
                endCloseTime = datetime.datetime(beginday.year, beginday.month, beginday.day, time[1].hour, time[1].minute)
                SubTimeSet.append([beginCloseTime - flytime, endCloseTime - flytime])
            beginday = beginday + datetime.timedelta(days = 1)
    #将InitialTime去掉SubTimeSet中的时间来作为可以起飞的区间
    for subtime in SubTimeSet:
        InitialTime = TimeSub(InitialTime, subtime)
    #判断最终结果，防止因为开始结果为minTime导致调机时间过早
    if InitialTime:
        if InitialTime[-1][0].year != 2017:
            return InitialTime[-1][1], InitialTime[-1][1] + flytime
        else:
            return InitialTime[-1][0], InitialTime[-1][0] + flytime
    return None, None

#寻找调机方案（快速）
def findferryplan(nums):
    l = len(nums)
    index = 0
    num_mat = [[0 for i in range(l)] for j in range(l)]
    res = []
    minnum = 0
    while(minnum < l + 1):
    #构建数量矩阵
        minnum = l + 1
        minloc = [0, 0]
        for i in range(l):
            for j in range(l):
                if nums[i][j] == 1:
                    num_mat[i][j] = min(sum(nums[i]), sum([nums[k][j] for k in range(l)]))
                    if num_mat[i][j] < minnum:
                        minnum = num_mat[i][j]
                        minloc = [i, j]
        for k in range(l):
            nums[minloc[0]][k] = 0
            nums[k][minloc[1]] = 0
        res.append(minloc)
    return res[:-1]

#寻找调机方案（DFS，成本最少）
def findferryplan2(nums, pairnum, tmp, res, cost, costs):
    if cost > res[0]:
        return []
    l = len(nums)
    sumnums = sum([sum(a) for a in nums])
    if sumnums == 0:
        if pairnum == l:
            if cost < res[0]:
                res[0] = cost
                res[1] = tmp
        return []

    for i in range(l):
        for j in range(l):
            if nums[i][j] == 1:
                cost_new = cost + costs[i][j]
                nums_copy = copy.deepcopy(nums)
                for k in range(l):
                    nums_copy[i][k] = 0
                    nums_copy[k][j] = 0
                findferryplan2(nums_copy, pairnum + 1, tmp + [[i, j]], res, cost_new, costs)
    return res[1]

#得到调机方案
def GetFerryPlan(Flight, FlightExecuteList, FlightDismissList, delayD, DomesticSet, FlightD, AirportCloseD, FlytimeD, Scene, AirplaneLimit):
    ExecuteList = []
    DismissList = []
    startports = []
    starttimes = []
    endports = []
    endtimes = []
    minTime = datetime.datetime(2000, 1, 1, 1, 1)
    maxTime = datetime.datetime(2100, 1, 1, 1, 1)

    ferrydimisscost = 0
    ferrydimisslist = []

    for i in range(len(FlightExecuteList)):
        if FlightExecuteList[i][0][3] == 0:
            #让ef的最后一个机场是国内机场
            while(FlightExecuteList[i][1]):
                if FlightD[FlightExecuteList[i][1][-1]][5] in DomesticSet:
                    break
                else:
                    ferrydimisslist += [FlightExecuteList[i][1][-1]]
                    FlightExecuteList[i][1] = FlightExecuteList[i][1][:-1]
            ef = FlightExecuteList[i]
            ExecuteList.append(i)
            if ef[1]:
                startports.append(FlightD[ef[1][-1]][5])
                starttimes.append(FlightD[ef[1][-1]][3] + delayD.get(ef[1][-1], datetime.timedelta(minutes = 0)))
            else:
                startports.append(ef[0][2])
                starttimes.append(minTime)

    for i in range(len(FlightDismissList)):
        if FlightDismissList[i][0][2] == 1:
            df = FlightDismissList[i]
            if df[1]:
                DismissList.append(i)
                endports.append(FlightD[df[1][0]][4])
                endtimes.append(FlightD[df[1][0]][2] + delayD.get(df[1][0], datetime.timedelta(minutes = 0)))
            else:
                #将空的串能不用调机的直接连上
                if df[0][3] in startports:
                    index = startports.index(df[0][3])
                    startports.remove(df[0][3])
                    starttimes.remove(starttimes[index])
                    FlightExecuteList[ExecuteList[index]][0][3] = 1
                    FlightDismissList[i][0][2] = 0
                    ExecuteList.remove(ExecuteList[index])  
                else:
                    DismissList.append(i)
                    endports.append(df[0][3])
                    endtimes.append(maxTime)

    l = len(ExecuteList)
    #构造调机可行矩阵
    FerryMat = [[0 for i in range(l)] for j in range(l)]
    Ferryloc = [[0 for i in range(l)] for j in range(l)]
    Ferrystarttime = [[0 for i in range(l)] for j in range(l)]
    Ferryendtime = [[0 for i in range(l)] for j in range(l)]
    Ferryports = [[0 for i in range(l)] for j in range(l)]
    costs = [[0 for i in range(l)] for j in range(l)]
    record = []

    for i in range(l):
        ef = FlightExecuteList[ExecuteList[i]]
        airtype = FlightExecuteList[ExecuteList[i]][0][1]
        for j in range(l):
            df = FlightDismissList[DismissList[j]]

            for h in range(len(ef[1]) - 1, -1, -1):
                f1 = ef[1][h]
                if FerryMat[i][j] == 1:
                    break
                for k in range(len(df[1])):
                    f2 = df[1][k]
                    if IsAirLimit(ef[0][0], df[1][k:], FlightD, AirplaneLimit) or (FlightD[f1][5], FlightD[f2][4], ef[0][0]) in AirplaneLimit or not(FlightD[f2][4] in DomesticSet) or not(FlightD[f1][5] in DomesticSet):
                        FerryMat[i][j] == 0
                    # elif df[0][1] != ef[0][1]:
                    #     FerryMat[i][j] == 0
                    else:
                        Ferrystarttime[i][j], Ferryendtime[i][j] = GetFerryTime(FlightD[f1][3] + delayD.get(f1, datetime.timedelta(minutes = 0)), FlightD[f2][2] + delayD.get(f2, datetime.timedelta(minutes = 0)), airtype, FlightD[f1][5], FlightD[f2][4], AirportCloseD, FlytimeD, Scene)
                        if Ferrystarttime[i][j]:
                            dimissl = ef[1][h+1: ] + df[1][:k]
                            cost = 0
                            for f in ef[1][h+1:]:
                                cost += FlightD[f][6] * 1000
                            for f in df[1][:k]:
                                    cost += FlightD[f][6] * 1000
                            if df[0][1] != ef[0][1]:
                                for f in df[1][k:]:
                                    cost += FlightD[f][6] * 1000
                            costs[i][j] = cost
                            FerryMat[i][j] = 1
                            Ferryloc[i][j] = [h, k]
                            Ferryports[i][j] = [FlightD[f1][5], FlightD[f2][4]]
                            break
                if FerryMat[i][j] == 0:
                    if (FlightD[f1][5], df[0][3], ef[0][0]) in AirplaneLimit or not(df[0][3] in DomesticSet) or not(FlightD[f1][5] in DomesticSet):
                        continue
                    #当机场相同时
                    if df[0][3] == FlightD[f1][5]:
                        cost = 0
                        for f in ef[1][h+1:]:
                            cost += FlightD[f][6] * 1000
                        for f in df[1]:
                            cost += FlightD[f][6] * 1000
                        cost -= 5000
                        costs[i][j] = cost
                        FerryMat[i][j] = 1
                        Ferryloc[i][j] = [h, -1]
                        Ferryports[i][j] = [FlightD[f1][5], df[0][3]]
                    else:
                        Ferrystarttime[i][j], Ferryendtime[i][j] = GetFerryTime(FlightD[f1][3] + delayD.get(f1, datetime.timedelta(minutes = 0)), maxTime, airtype, FlightD[f1][5], df[0][3], AirportCloseD, FlytimeD, Scene)
                        if Ferrystarttime[i][j]:
                            dimissl = ef[1][h+1: ] + df[1]
                            cost = 0
                            for f in ef[1][h+1:]:
                                cost += FlightD[f][6] * 1000
                            for f in df[1]:
                                cost += FlightD[f][6] * 1000
                            costs[i][j] = cost
                            FerryMat[i][j] = 1
                            Ferryloc[i][j] = [h, -1]
                            Ferryports[i][j] = [FlightD[f1][5], df[0][3]]
                            break
    for m in FerryMat:
        print(m)
    #获得调机方案
    if l <= 6:
        ferrysolution = findferryplan2(FerryMat, 0, [], [100000000, []], 0, costs)
    else:
        ferrysolution = findferryplan(FerryMat)

    for ferry in ferrysolution:
        k = Flight.shape[0]
        el = Ferryloc[ferry[0]][ferry[1]][0]
        dl = Ferryloc[ferry[0]][ferry[1]][1]
        #当调机开始机场与结束机场相同时，不需要调机
        if Ferryports[ferry[0]][ferry[1]][0] == Ferryports[ferry[0]][ferry[1]][1]:
            FlightExecuteList[ExecuteList[ferry[0]]][1] = FlightExecuteList[ExecuteList[ferry[0]]][1][:el + 1]
            continue
        Flight.ix[k] = [k + 1, 0, "国内", k, Ferryports[ferry[0]][ferry[1]][0], Ferryports[ferry[0]][ferry[1]][1], Ferrystarttime[ferry[0]][ferry[1]],  Ferryendtime[ferry[0]][ferry[1]], FlightExecuteList[ExecuteList[ferry[0]]][0][0], 1, 1, 0]
        if dl != -1:
            ferrydimisslist += FlightExecuteList[ExecuteList[ferry[0]]][1][el + 1:]
            ferrydimisslist += FlightDismissList[DismissList[ferry[1]]][1][:dl]

            FlightExecuteList[ExecuteList[ferry[0]]][1] = FlightExecuteList[ExecuteList[ferry[0]]][1][:el + 1] + [k + 1] + FlightDismissList[DismissList[ferry[1]]][1][dl:]
        else:
            ferrydimisslist += FlightExecuteList[ExecuteList[ferry[0]]][1][el + 1:] + FlightDismissList[DismissList[ferry[1]]][1]

            FlightExecuteList[ExecuteList[ferry[0]]][1] = FlightExecuteList[ExecuteList[ferry[0]]][1][:el + 1] + [k + 1]

        FlightExecuteList[ExecuteList[ferry[0]]][0][3] = 1
        FlightDismissList[DismissList[ferry[1]]][0][2] = 0
    if len(ferrysolution) == l:
        for f in ferrydimisslist:
            ferrydimisscost += FlightD[f][6] * 1000
        print("调机数量为：", l)
        print("调机取消飞机个数为：", len(ferrydimisslist))
        print("调机取消飞机费用为：", ferrydimisscost)
        return True

#根据FlyD得到调机方案
def GetFerryPlan2(Flight, FlightExecuteList, FlightDismissList, delayD, DomesticSet, FlightD, AirportCloseD, FlytimeD, Scene, AirplaneLimit):
    
    minTime = datetime.datetime(2000, 1, 1, 1, 1)
    maxTime = datetime.datetime(2100, 1, 1, 1, 1)

    FlightExecuteListcopy = copy.deepcopy(FlightExecuteList)
    FlightDismissListcopy = copy.deepcopy(FlightDismissList)
    Flightcopy = Flight.copy()
    #统计需要调机去的机场
    endports = []
    for i in range(len(FlightDismissListcopy)):
        if FlightDismissListcopy[i][0][2] == 1:
            df = FlightDismissListcopy[i]
            endports.append(df[0][3])
    #调机操作
    le = len(FlightExecuteListcopy)
    for i in range(le):
        if FlightExecuteListcopy[i][0][3] == 1:
            continue
        ef = FlightExecuteListcopy[i]
        lef = len(ef[1])
        minef = []
        minsolute = []
        time = []
        port = []
        minendport = 0
        maxsubcost = -1000000
        FlightDismissListcopy = splitSolution(FlightD, FlightDismissListcopy)
        FlyD = CreateflyD2(FlightD, Scene, FlightDismissListcopy, delayD)
        for j in range(lef - 1, -1, -1):
            if not (FlightD[ef[1][j]][5] in DomesticSet):
                continue
            for endport in endports:
                for k in range(1, 80):
                    if (FlightD[ef[1][j]][5], k, ef[0][0]) in AirplaneLimit:
                        continue
                    solute = copy.deepcopy(FlyD.get((k, endport, ef[0][1]), []))
                    for s in solute:
                        fset = []
                        for h in s:
                            fset = fset + FlightDismissListcopy[h][1]
                        #print(j, k, endport, fset)
                        if not (FlightD[fset[0]][4] in DomesticSet):
                            continue
                        if IsAirLimit(ef[0][0], fset, FlightD, AirplaneLimit):
                            continue
                        Ferrystarttime, Ferryendtime = GetFerryTime(FlightD[ef[1][j]][3] + delayD.get(ef[1][j], datetime.timedelta(minutes = 0)), FlightD[fset[0]][2] + delayD.get(fset[0], datetime.timedelta(minutes = 0)), ef[0][1], FlightD[ef[1][j]][5], FlightD[fset[0]][4], AirportCloseD, FlytimeD, Scene)
                        if Ferrystarttime:
                            #计算成本
                            subcost = 0
                            for f in fset:
                                if FlightD[f][7] == ef[0][1]:
                                    subcost += FlightD[f][6] * 1000
                                #subcost += FlightD[f][6] * 1000
                                subcost -= FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            for f in ef[1][j + 1:]:
                                if FlightD[f][7] == ef[0][1]:
                                    subcost -= FlightD[f][6] * 1000
                                #subcost -= FlightD[f][6] * 1000
                                subcost += FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            subcost -= 5000
                            if subcost > maxsubcost:
                                maxsubcost = subcost
                                minef = [ef[1][:j + 1], fset]
                                port = [FlightD[ef[1][j]][5], FlightD[fset[0]][4]]
                                time = [Ferrystarttime, Ferryendtime]
                                minsolute = s
                                minendport = endport
                #若不用调机
                if FlightD[ef[1][j]][5] == endport:
                    subcost = 0
                    for f in ef[1][j + 1:]:
                        if FlightD[f][7] == ef[0][1]:
                            subcost -= FlightD[f][6] * 1000
                        subcost += FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                    if subcost > maxsubcost:
                        maxsubcost = subcost
                        minef = ef[1][:j + 1]
                        time = []
                        port = []
                        minsolute = []
                        minendport = endport
                #直接调机
                else:
                    if not (endport in DomesticSet):
                        continue
                    if (FlightD[ef[1][j]][5], endport, ef[0][0]) in AirplaneLimit:
                        continue
                    Ferrystarttime, Ferryendtime = GetFerryTime(FlightD[ef[1][j]][3] + delayD.get(ef[1][j], datetime.timedelta(minutes = 0)), maxTime, ef[0][1], FlightD[ef[1][j]][5], endport, AirportCloseD, FlytimeD, Scene)
                    if Ferrystarttime:
                        subcost = 0
                        for f in ef[1][j + 1:]:
                            if FlightD[f][7] == ef[0][1]:
                                subcost -= FlightD[f][6] * 1000
                            subcost += FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                        subcost -= 5000
                        if subcost > maxsubcost:
                            maxsubcost = subcost
                            minef = [ef[1][:j + 1], []]
                            time = [Ferrystarttime, Ferryendtime]
                            port = [FlightD[ef[1][j]][5], endport]
                            minsolute = []
                            minendport = endport
        if maxsubcost == -1000000:
            break
        #调机
        if not port:
            FlightExecuteListcopy[i][1] = minef[:]
            #print(i)
        else:
            k = Flightcopy.shape[0]
            Flightcopy.ix[k] = [k + 1, 0, "国内", k, port[0], port[1], time[0], time[1], ef[0][0], 1, 1, 0]
            FlightExecuteListcopy[i][1] = minef[0] + [k + 1] + minef[1]
            for h in minsolute:
                FlightDismissListcopy[h][1] = []
        endports.remove(minendport)

    if not endports:
        return FlightExecuteListcopy, FlightDismissListcopy, Flightcopy

    #反向
    FlightExecuteListcopy = copy.deepcopy(FlightExecuteList)
    FlightDismissListcopy = copy.deepcopy(FlightDismissList)
    Flightcopy = Flight.copy()
    #统计需要调机去的机场
    endports = []
    for i in range(len(FlightDismissListcopy)):
        if FlightDismissListcopy[i][0][2] == 1:
            df = FlightDismissListcopy[i]
            endports.append(df[0][3])
    #调机操作
    le = len(FlightExecuteListcopy)
    for i in range(le - 1, -1, -1):
        if FlightExecuteListcopy[i][0][3] == 1:
            continue
        ef = FlightExecuteListcopy[i]
        lef = len(ef[1])
        minef = []
        minsolute = []
        time = []
        port = []
        minendport = 0
        maxsubcost = -1000000
        FlightDismissListcopy = splitSolution(FlightD, FlightDismissListcopy)
        FlyD = CreateflyD(FlightD, Scene, FlightDismissListcopy, delayD)
        for j in range(lef - 1, -1, -1):
            if not (FlightD[ef[1][j]][5] in DomesticSet):
                continue
            for endport in endports:
                for k in range(1, 80):
                    if (FlightD[ef[1][j]][5], k, ef[0][0]) in AirplaneLimit:
                        continue
                    solute = copy.deepcopy(FlyD.get((k, endport, ef[0][1]), []))
                    for s in solute:
                        fset = []
                        for h in s:
                            fset = fset + FlightDismissListcopy[h][1]
                        #print(j, k, endport, fset)
                        if not (FlightD[fset[0]][4] in DomesticSet):
                            continue
                        if IsAirLimit(ef[0][0], fset, FlightD, AirplaneLimit):
                            continue
                        Ferrystarttime, Ferryendtime = GetFerryTime(FlightD[ef[1][j]][3] + delayD.get(ef[1][j], datetime.timedelta(minutes = 0)), FlightD[fset[0]][2] + delayD.get(fset[0], datetime.timedelta(minutes = 0)), ef[0][1], FlightD[ef[1][j]][5], FlightD[fset[0]][4], AirportCloseD, FlytimeD, Scene)
                        if Ferrystarttime:
                            #计算成本
                            subcost = 0
                            for f in fset:
                                subcost += FlightD[f][6] * 1000
                                subcost -= FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            for f in ef[1][j + 1:]:
                                subcost -= FlightD[f][6] * 1000
                                subcost += FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                            subcost -= 5000
                            if subcost > maxsubcost:
                                maxsubcost = subcost
                                minef = [ef[1][:j + 1], fset]
                                port = [FlightD[ef[1][j]][5], FlightD[fset[0]][4]]
                                time = [Ferrystarttime, Ferryendtime]
                                minsolute = s
                                minendport = endport
                #若不用调机
                if FlightD[ef[1][j]][5] == endport:
                    subcost = 0
                    for f in ef[1][j + 1:]:
                        subcost -= FlightD[f][6] * 1000
                        subcost += FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                    if subcost > maxsubcost:
                        maxsubcost = subcost
                        minef = ef[1][:j + 1]
                        time = []
                        port = []
                        minsolute = []
                        minendport = endport
                #直接调机
                else:
                    if not (endport in DomesticSet):
                        continue
                    if (FlightD[ef[1][j]][5], endport, ef[0][0]) in AirplaneLimit:
                        continue
                    Ferrystarttime, Ferryendtime = GetFerryTime(FlightD[ef[1][j]][3] + delayD.get(ef[1][j], datetime.timedelta(minutes = 0)), maxTime, ef[0][1], FlightD[ef[1][j]][5], endport, AirportCloseD, FlytimeD, Scene)
                    if Ferrystarttime:
                        subcost = 0
                        for f in ef[1][j + 1:]:
                            subcost -= FlightD[f][6] * 1000
                            subcost += FlightD[f][6] * 100 * (delayD.get(f, datetime.timedelta(minutes = 0)) / datetime.timedelta(hours = 1))
                        subcost -= 5000
                        if subcost > maxsubcost:
                            maxsubcost = subcost
                            minef = [ef[1][:j + 1], []]
                            time = [Ferrystarttime, Ferryendtime]
                            port = [FlightD[ef[1][j]][5], endport]
                            minsolute = []
                            minendport = endport
        if maxsubcost == -1000000:
            break
        #调机
        if not port:
            FlightExecuteListcopy[i][1] = minef[:]
        else:
            k = Flightcopy.shape[0]
            Flightcopy.ix[k] = [k + 1, 0, "国内", k, port[0], port[1], time[0], time[1], ef[0][0], 1, 1, 0]
            FlightExecuteListcopy[i][1] = minef[0] + [k + 1] + minef[1]
            for h in minsolute:
                FlightDismissListcopy[h][1] = []
        endports.remove(minendport)

    if not endports:
        return FlightExecuteListcopy, FlightDismissListcopy, Flightcopy
    return [],[],[]

#检查方案是否全局基地平衡，测试用
def check(oldFlight, FlightExecuteList, FlightDismissList):
    oldFlight = oldFlight.sort_values(['airplaneId', 'startDateTime'])
    oldFlight = oldFlight.reset_index(drop = True)

    airplaneNow = 1
    endport = [0] * 80
    for i in oldFlight.index:
        #换飞机时   
        if oldFlight['airplaneId'][i] != airplaneNow:
            endport[oldFlight['endAirport'][i - 1]] += 1
            airplaneNow = oldFlight['airplaneId'][i]
    endport[oldFlight['endAirport'][i]] += 1


    endport2 = [0] * 80
    for ef in FlightExecuteList:
        if ef[0][3] == 1:
            if ef[1]:
                endport2[FlightD[ef[1][-1]][5]] += 1
            else:
                endport2[ef[0][3]] += 1

    for df in FlightDismissList:
        if df[0][2] == 1:
            if df[1]:
                endport2[FlightD[df[1][-1]][5]] += 1
            else:
                endport2[df[0][3]] += 1

    index = 0
    for i in range(80):
        if endport[i] != endport2[i]:
            print(i)
            index = 1
    if index == 0:
        print("endport is right!")

#整理FlightDismissList，把零散的变为长串
def sortSolution(FlightD, FlightDismissList, delayD, Scene):
    index = 1
    while(index == 1):
        index = 0
        FlightDismissList = [df for df in FlightDismissList if df[1] or df[0][2] == 1]
        for i in range(len(FlightDismissList)):
            df = FlightDismissList[i]
            if df[0][2] == 1:
                continue
            if not df[1]:
                continue
            #获得开始时间，开始机场
            closest = -1
            closetime = datetime.timedelta(days = 10)
            starttime = FlightD[df[1][-1]][3] + delayD.get(df[1][-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50)
            startport = FlightD[df[1][-1]][5]
            if startport in (49, 50, 61):# and FlightD[df[1][-1]][3] < Scene.ix[0][1]:
                continue
            #寻找可向df后面插的串
            for j in range(len(FlightDismissList)):
                if i == j:
                    continue
                df2 = FlightDismissList[j]
                if df[0][1] != df2[0][1]:
                    continue
                if not df2[1]:
                    continue
                if FlightD[df2[1][0]][4] != startport:
                    continue
                if FlightD[df2[1][0]][2] + delayD.get(df2[1][0], datetime.timedelta(minutes = 0)) < starttime:
                    continue
                index = 1
                timedistance = FlightD[df2[1][0]][2] + delayD.get(df2[1][0], datetime.timedelta(minutes = 0)) - starttime
                if timedistance < closetime:
                    closetime = timedistance
                    closest = j
            if closest != -1:
                index = 1
                FlightDismissList[i][1] = df[1] + FlightDismissList[closest][1]
                FlightDismissList[closest][1] = []
                FlightDismissList[i][0][2] = FlightDismissList[closest][0][2]
                FlightDismissList[closest][0][2] = 0
                FlightDismissList[i][0][3] = FlightDismissList[closest][0][3]
    return FlightDismissList

#将Solution分割为单个航班或者联程航班为单位的新方法
def splitSolution(FlightD, FlightDismissList):
    NewFlightDismissList = []
    for df in FlightDismissList:
        i = 0
        ldf = len(df[1])
        if ldf == 0 and df[0][2] == 1:
            dfcopy = copy.deepcopy(df)
            NewFlightDismissList.append(dfcopy)
        while(i < len(df[1])):
            if i == ldf - 1:
                NewFlightDismissList.append([df[0], [df[1][i]]])
                i += 1
            else:
                if FlightD[df[1][i]][1] != 0 and FlightD[df[1][i]][1] == FlightD[df[1][i + 1]][1]:
                    if i == ldf - 2:
                        NewFlightDismissList.append([df[0], df[1][i:i+2]])
                    else:
                        NewFlightDismissList.append([[df[0][0], df[0][1], 0, 0], df[1][i:i+2]])
                    i += 2
                else:
                    NewFlightDismissList.append([[df[0][0], df[0][1], 0, 0], [df[1][i]]])
                    i += 1
    return NewFlightDismissList

#创建航班起始终止机场航班字典
def CreateflyD(FlightD, Scene, FlightDismissList, delayD):
    mat = [[[] for i in range(80)] for j in range(80)]
    l = len(FlightDismissList)
    for i in range(l):
        df = FlightDismissList[i]
        if not df[1]:
            continue
        startport = FlightD[df[1][0]][4]
        endport = FlightD[df[1][-1]][5]
        starttime = FlightD[df[1][0]][2] + delayD.get(df[1][0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50)
        endtime = FlightD[df[1][-1]][3] + delayD.get(df[1][-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50)
        mat[startport][endport].append([i])
        for j in range(1, 80):
            for list1 in mat[endport][j]:
                #飞机型号一样
                if df[0][1] == FlightDismissList[list1[0]][0][1]:
                    #时间满足
                    f = FlightDismissList[list1[0]][1][0]
                    if FlightD[f][2] + delayD.get(f, datetime.timedelta(minutes = 0)) >= endtime:
                        #台风不能停机满足
                        if not (endport in (49, 50, 61)) or IsTimeSameRange(endtime, FlightD[f][2] + delayD.get(f, datetime.timedelta(minutes = 0)), 0, Scene):
                            mat[startport][j].append([i] + list1)
            for list2 in mat[j][startport]:
                #飞机型号一样
                if df[0][1] == FlightDismissList[list2[0]][0][1]:
                    #时间满足
                    f = FlightDismissList[list2[-1]][1][-1]
                    if FlightD[f][3] + delayD.get(f, datetime.timedelta(minutes = 0)) <= starttime:
                        #台风不能停机满足
                        if not (startport in (49, 50, 61)) or IsTimeSameRange(starttime, FlightD[f][3] + delayD.get(f, datetime.timedelta(minutes = 0)), 0, Scene):
                            mat[j][endport].append(list2 + [i])

    d = {}
    for i in range(1, 80):
        for j in range(1, 80):
            for list1 in mat[i][j]:
                if (i, j, FlightDismissList[list1[0]][0][1]) in d:
                    d[(i, j, FlightDismissList[list1[0]][0][1])].append(list1)
                else:
                    d[(i, j, FlightDismissList[list1[0]][0][1])] = [list1]
    return d

def CreateflyD2(FlightD, Scene, FlightDismissList, delayD):
    mat = [[[] for i in range(80)] for j in range(80)]
    l = len(FlightDismissList)
    for i in range(l):
        df = FlightDismissList[i]
        if not df[1]:
            continue
        startport = FlightD[df[1][0]][4]
        endport = FlightD[df[1][-1]][5]
        starttime = FlightD[df[1][0]][2] + delayD.get(df[1][0], datetime.timedelta(minutes = 0)) - datetime.timedelta(minutes = 50)
        endtime = FlightD[df[1][-1]][3] + delayD.get(df[1][-1], datetime.timedelta(minutes = 0)) + datetime.timedelta(minutes = 50)
        mat[startport][endport].append([i])
        for j in range(1, 80):
            for list1 in mat[endport][j]:
                #时间满足
                f = FlightDismissList[list1[0]][1][0]
                if FlightD[f][2] + delayD.get(f, datetime.timedelta(minutes = 0)) >= endtime:
                    #台风不能停机满足
                    if not (endport in (49, 50, 61)) or IsTimeSameRange(endtime, FlightD[f][2] + delayD.get(f, datetime.timedelta(minutes = 0)), 0, Scene):
                        mat[startport][j].append([i] + list1)
            for list2 in mat[j][startport]:
                #时间满足
                f = FlightDismissList[list2[-1]][1][-1]
                if FlightD[f][3] + delayD.get(f, datetime.timedelta(minutes = 0)) <= starttime:
                    #台风不能停机满足
                    if not (startport in (49, 50, 61)) or IsTimeSameRange(starttime, FlightD[f][3] + delayD.get(f, datetime.timedelta(minutes = 0)), 0, Scene):
                        mat[j][endport].append(list2 + [i])

    d = {}
    for i in range(1, 80):
        for j in range(1, 80):
            for list1 in mat[i][j]:
                if (i, j, FlightDismissList[list1[0]][0][1]) in d:
                    d[(i, j, FlightDismissList[list1[0]][0][1])].append(list1)
                else:
                    d[(i, j, FlightDismissList[list1[0]][0][1])] = [list1]
    return d


#得到可以通过推迟10小时内运行的航班，返回一个新的DF表与一个延迟时间字典
def GetExtraFlight(delayDinput, FlightD, FlightDismissList, AirportCloseD, Scene):
    NewStartTime = Scene.ix[0][1] + datetime.timedelta(minutes = 50)
    NewEndTime = Scene.ix[0][1]
    delayD = delayDinput.copy()
    DF = copy.deepcopy(FlightDismissList)
    Dealedflightset = set()
    k = 10000
    for f in FlightD:
        #筛选已取消且联程不在未取消中的航班
        if FlightD[f][1] == 1 and FlightD[f][8] != 0:
            #若为联程航班
            if FlightD[f][9] != 0:
                jointf = FlightD[f][9]
                if FlightD[f][3] > FlightD[jointf][2]:
                    continue
                #确定第一个航班的延迟时间
                if FlightD[f][4] in (49, 50, 61):
                    delaytime1 = NewStartTime - FlightD[f][2]
                else:
                    delaytime1 = NewEndTime - FlightD[f][3]
                if delaytime1 > datetime.timedelta(hours = 12):
                    continue
                #改变字典的值
                FlightD[f][1] = k
                FlightD[jointf][1] = k
                k += 1
                #确定第二个航班的开始时间
                starttime2 = NewEndTime + min(datetime.timedelta(minutes = 50), FlightD[jointf][2] - FlightD[f][3])
                delaytime2 = starttime2 - FlightD[jointf][2]
                delayD[f] = delaytime1
                delayD[jointf] = delaytime2
                DF.append([[0, FlightD[f][7], 0, 0], [f, jointf]])
            else:
                #分两类，一类是起始机场受影响，一类是结束机场受影响
                if FlightD[f][4] in (49, 50, 61):
                    #判断时间
                    delaytime = NewStartTime - FlightD[f][2]
                    if delaytime > datetime.timedelta(hours = 10):
                        continue
                    endtime = FlightD[f][3] + delaytime
                    if IsAirportClose(AirportCloseD, FlightD[f][5], endtime):
                        continue
                    #将延迟时间与航班加入DF与延迟时间表中
                    delayD[f] = delaytime
                    DF.append([[0, FlightD[f][7], 0, 0], [f]])
                else:
                    delaytime = NewEndTime - FlightD[f][3]
                    if delaytime > datetime.timedelta(hours = 10):
                        continue
                    starttime = FlightD[f][2] + delaytime
                    if IsAirportClose(AirportCloseD, FlightD[f][4], starttime):
                        continue
                    delayD[f] = delaytime
                    DF.append([[0, FlightD[f][7], 0, 0], [f]])
    return DF, delayD

#将联程航班拉直
def Straightflight(DomesticJoint, FlytimeD, FlightD, FlightExecuteList, FlightDismissList, delayD):
    l = 0
    #统计EF中的航班
    efset = set()
    for ef in FlightExecuteList:
        for f in ef[1]:
            efset.add(f)
    #拉直
    DFremoveset = set()
    for f in DomesticJoint:
        if f in efset or DomesticJoint[f] in efset:
            continue
        startport = FlightD[f][4]
        endport = FlightD[DomesticJoint[f]][5]
        flytime = FlytimeD.get((FlightD[f][7], startport, endport), 0)
        if flytime == 0:
            flytime = FlightD[f][3] - FlightD[f][2] + (FlightD[DomesticJoint[f]][3] - FlightD[DomesticJoint[f]][2])
        else:
            flytime = datetime.timedelta(minutes = int(flytime))

        FlightD[f][3] = FlightD[f][2] + flytime
        FlightD[f][5] = endport
        FlightD[f][8] = 0
        FlightD[f][10] = 1
        delayD[f] = datetime.timedelta(minutes = 0)

        FlightD[DomesticJoint[f]][8] = 1
        FlightD[DomesticJoint[f]][10] = 1
        DFremoveset.add(DomesticJoint[f])
        l += 1
    #在DF中去掉
    for i in range(len(FlightDismissList)):
        for f in FlightDismissList[i][1]:
            if f in DFremoveset:
                FlightDismissList[i][1].remove(f)
    print("拉直的联程航班有：", l, "班")
    return FlightExecuteList, FlightDismissList, delayD, FlightD


def delay(FlightDismissList, delayD):
    dfset = []
    for df in FlightDismissList:
        for f in df[1]:
            dfset.append(f)
    k = 0
    fdelayset = random.sample(dfset, 5)

    for f in fdelayset:
        delaytime = random.randint(0, 150)
        delayD[f] = delayD.get(f, datetime.timedelta(hours = 0)) + datetime.timedelta(minutes = delaytime)
    return delayD


#GRASP算法，下降方向采取最大下降方向
def GRASP(FlightExecuteList, FlightDismissList, delayD, initialCost, FlightD, AirplaneLimit, Scene, mode, delayMaxhour, KTimes, period, delayDcompare, AirportCloseD):
    DownRCL = [[initialCost, FlightExecuteList, FlightDismissList, delayD]]
    UpRcl = []
    k = 0
    num = 0
    mincost = initialCost
    minSolution = [FlightExecuteList, FlightDismissList, delayD]
    FlyD = {}
    FlyDEnable = 0
    DownEnable = 1
    if mode == 0:
        k = 0
        while(k < KTimes):
            k += 1
            #DownRCL池不空
            DownRCLSize = len(DownRCL)
            if DownRCLSize != 0:
                #i = random.randint(0, DownRCLSize - 1)
                cost = [DownRCL[i][0] for i in range(DownRCLSize)]
                i = cost.index(min(cost))
                if mincost > DownRCL[i][0]:
                    mincost = DownRCL[i][0]
                    minSolution = copy.deepcopy([DownRCL[i][1], DownRCL[i][2], DownRCL[i][3]])
                print(k, DownRCLSize, mincost)
                DownRCL[i][2] = sortSolution(FlightD, DownRCL[i][2], DownRCL[i][3], Scene)
                DownRCL, UpRcl = GRASPOnce(DownRCL[i][1], DownRCL[i][2], DownRCL[i][0], DownRCL[i][3], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)
            else:
                print("No Down Solution:", num)
                num += 1
                if num == 5:
                    break
                minSolution[1] = sortSolution(FlightD, minSolution[1], minSolution[2], Scene)
                DownRCL, UpRcl = GRASPOnce(minSolution[0], minSolution[1], mincost, minSolution[2], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)
    if mode == 1:      
        k = 0
        num = 0
        while(k < KTimes):
            k += 1
            #DownRCL池不空
            DownRCLSize = len(DownRCL)
            if DownRCLSize != 0:
                #i = random.randint(0, DownRCLSize - 1)
                cost = [DownRCL[i][0] for i in range(DownRCLSize)]
                i = cost.index(min(cost))
                if mincost > DownRCL[i][0]:
                    mincost = DownRCL[i][0]
                    minSolution = copy.deepcopy([DownRCL[i][1], DownRCL[i][2], DownRCL[i][3]])
                print(k, DownRCLSize, mincost)
                DownRCL[i][2] = sortSolution(FlightD, DownRCL[i][2], DownRCL[i][3], Scene)
                DownRCL, UpRcl = GRASPOnce(DownRCL[i][1], DownRCL[i][2], DownRCL[i][0], DownRCL[i][3], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)
            else:
                if k % 100 == 0:
                    print(1, k)
                if k % period == 0:
                    DownEnable = 1
                else:
                    DownEnable = 0
                i = random.randint(0, len(UpRcl) - 1)
                # for j in range(len(UpRcl)):
                #     if len(UpRcl[j]) == 5:
                #         i = j
                UpRcl[i][2] = sortSolution(FlightD, UpRcl[i][2], UpRcl[i][3], Scene)
                DownRCL, UpRcl = GRASPOnce(UpRcl[i][1], UpRcl[i][2], UpRcl[i][0], UpRcl[i][3], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)

    if mode == 2:
        k = 0
        FlyDEnable = 1
        while(k < KTimes):
            k += 1
            #DownRCL池不空
            DownRCLSize = len(DownRCL)
            if DownRCLSize != 0:
                #i = random.randint(0, DownRCLSize - 1)
                cost = [DownRCL[i][0] for i in range(DownRCLSize)]
                i = cost.index(min(cost))
                if mincost > DownRCL[i][0]:
                    mincost = DownRCL[i][0]
                    minSolution = copy.deepcopy([DownRCL[i][1], DownRCL[i][2], DownRCL[i][3]])
                splitsolute = splitSolution(FlightD, DownRCL[i][2])
                FlyD = CreateflyD(FlightD, Scene, splitsolute, DownRCL[i][3])

                print(k, DownRCLSize, mincost)
                DownRCL, UpRcl = GRASPOnce(DownRCL[i][1], splitsolute, DownRCL[i][0], DownRCL[i][3], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)
            else:
                if k % 100 == 0:
                    print(2, k)
                if k % period == 0:
                    DownEnable = 1
                else:
                    DownEnable = 0
                i = random.randint(0, len(UpRcl) - 1)
                # for j in range(len(UpRcl)):
                #     if len(UpRcl[j]) == 5:
                #         i = j
                splitsolute = splitSolution(FlightD, UpRcl[i][2])
                FlyD = CreateflyD(FlightD, Scene, splitsolute, UpRcl[i][3])
                DownRCL, UpRcl = GRASPOnce(UpRcl[i][1], splitsolute, UpRcl[i][0], UpRcl[i][3], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)

    if mode == 3:
        k = 0
        FlyDEnable = 1
        while(k < KTimes):
            k += 1
            #DownRCL池不空
            DownRCLSize = len(DownRCL)
            if DownRCLSize != 0:
                #i = random.randint(0, DownRCLSize - 1)
                cost = [DownRCL[i][0] for i in range(DownRCLSize)]
                i = cost.index(min(cost))
                if mincost > DownRCL[i][0]:
                    mincost = DownRCL[i][0]
                    minSolution = copy.deepcopy([DownRCL[i][1], DownRCL[i][2], DownRCL[i][3]])
                splitsolute = splitSolution(FlightD, DownRCL[i][2])
                FlyD = CreateflyD2(FlightD, Scene, splitsolute, DownRCL[i][3])

                print(k, DownRCLSize, mincost)
                DownRCL, UpRcl = GRASPOnce(DownRCL[i][1], splitsolute, DownRCL[i][0], DownRCL[i][3], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)
            else:
                if k % 100 == 0:
                    print(2, k)
                if k % period == 0:
                    DownEnable = 1
                else:
                    DownEnable = 0
                i = random.randint(0, len(UpRcl) - 1)
                # for j in range(len(UpRcl)):
                #     if len(UpRcl[j]) == 5:
                #         i = j
                splitsolute = splitSolution(FlightD, UpRcl[i][2])
                FlyD = CreateflyD2(FlightD, Scene, splitsolute, UpRcl[i][3])
                DownRCL, UpRcl = GRASPOnce(UpRcl[i][1], splitsolute, UpRcl[i][0], UpRcl[i][3], FlightD, AirplaneLimit, Scene, num, FlyD, FlyDEnable, DownEnable, delayMaxhour, delayDcompare, AirportCloseD)

    return mincost, minSolution

#*******************************************************************************************
#从Excel表格中获得数据
Flight, AirplaneLimitation, AirportClose, Scene, TravelTime = GetOriginData()
oldFlight = Flight.copy()
#获得一些所需要的集合信息
DomesticSet, FlytimeD, AirplaneLimit, AirportCloseD = GetSets(Flight, TravelTime, AirplaneLimitation, AirportClose)

#**********************************
hour = 4
#**********************************
#初始解

FlightD, FlightExecuteList, FlightDismissList, initialCost, initialdelayD, Flight, DomesticJoint, delayDcompare = GetInitialSolution(Flight, Scene, AirportCloseD, hour)
FlightDismissListcopy = copy.deepcopy(FlightDismissList)

#使用GRASP进行处理,第一遍获得局部最优
k = 18000
p = 30
delayMaxhour1 = 4
mincost1, minSolution1 = GRASP(FlightExecuteList, FlightDismissList, initialdelayD, initialCost, FlightD, AirplaneLimit, Scene, 0, delayMaxhour1, k, p, delayDcompare, AirportCloseD)

#第二遍，不拆分DF，进行领域寻找下降解
k = 18000
p = 30
delayMaxhour2 = 4
m10 = copy.deepcopy(minSolution1[0])
m11 = copy.deepcopy(minSolution1[1])
m12 = copy.deepcopy(minSolution1[2])
mincost2, minSolution2 = GRASP(m10, m11, m12, mincost1, FlightD, AirplaneLimit, Scene, 1, delayMaxhour2, k, p, delayDcompare, AirportCloseD)

#拆分DF，把航程拉直，邻域寻找下降解
k = 18000
p = 30
delayMaxhour3 = 4
m20 = copy.deepcopy(minSolution2[0])
m21 = copy.deepcopy(minSolution2[1])
m22 = copy.deepcopy(minSolution2[2])
m20, m21, m22, FlightD = Straightflight(DomesticJoint, FlytimeD, FlightD, m20, m21, m22)
mincost3, minSolution3 = GRASP(m20, m21, m22, mincost2, FlightD, AirplaneLimit, Scene, 2, delayMaxhour3, k, p, delayDcompare, AirportCloseD)

#将取消的10h内的航班加入到DF中，邻域寻找下降解
k = 18000
p = 30
delayMaxhour4 = 4
m30 = copy.deepcopy(minSolution3[0])
m31 = copy.deepcopy(minSolution3[1])
m32 = copy.deepcopy(minSolution3[2])
DF, delayD = GetExtraFlight(m32, FlightD, m31, AirportCloseD, Scene)
m31copy = copy.deepcopy(m31)
FlightDcopy = copy.deepcopy(FlightD)
x, delayDcompare = GetExtraFlight(delayDcompare, FlightDcopy, m31copy, AirportCloseD, Scene)
mincost4, minSolution4 = GRASP(m30, DF, delayD, mincost3, FlightD, AirplaneLimit, Scene, 2, delayMaxhour4, k, p, delayDcompare, AirportCloseD)

#允许不同机型
k = 10000
p = 100
delayMaxhour5 = 6
m40 = copy.deepcopy(minSolution4[0])
m41 = copy.deepcopy(minSolution4[1])
m42 = copy.deepcopy(minSolution4[2])
mincost5, minSolution5 = GRASP(m40, m41, m42, mincost4, FlightD, AirplaneLimit, Scene, 3, delayMaxhour5, k, p, delayDcompare, AirportCloseD)


#调机,生成最终解
Flightwithferry = Flight.copy()
mk0 = copy.deepcopy(minSolution5[0])
mk1 = copy.deepcopy(minSolution5[1])
mk2 = copy.deepcopy(minSolution5[2])

mres0, mres1, flightres =  GetFerryPlan2(Flightwithferry, mk0, mk1, mk2,  DomesticSet, FlightD, AirportCloseD, FlytimeD, Scene, AirplaneLimit)
if mres0:
    GetResult(flightres, [mres0, mres1], FlightD, mk2, DomesticJoint)
else:
    if GetFerryPlan(Flightwithferry, mk0, mk1, mk2,  DomesticSet, FlightD, AirportCloseD, FlytimeD, Scene, AirplaneLimit):
        Flightwithferry = GetResult(Flightwithferry, [mk0, mk1], FlightD, mk2, DomesticJoint)


# if GetFerryPlan(Flightwithferry, mk0, mk1, mk2,  DomesticSet, FlightD, AirportCloseD, FlytimeD, Scene, AirplaneLimit):
#     Flightwithferry = GetResult(Flightwithferry, [mk0, mk1], FlightD, mk2, DomesticJoint)


#统计****************************************************
print(hour, "小时")

print("总取消飞机个数为：", Flightwithferry[Flightwithferry["isCancel"] != 0].shape[0])
