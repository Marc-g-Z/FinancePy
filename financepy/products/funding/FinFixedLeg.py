##############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
##############################################################################

from ...finutils.FinError import FinError
from ...finutils.FinDate import FinDate
from ...finutils.FinMath import ONE_MILLION
from ...finutils.FinGlobalVariables import gSmall
from ...finutils.FinDayCount import FinDayCount, FinDayCountTypes
from ...finutils.FinFrequency import FinFrequencyTypes, FinFrequency
from ...finutils.FinCalendar import FinCalendarTypes,  FinDateGenRuleTypes
from ...finutils.FinCalendar import FinCalendar, FinBusDayAdjustTypes
from ...finutils.FinSchedule import FinSchedule
from ...finutils.FinHelperFunctions import labelToString, checkArgumentTypes
from ...finutils.FinGlobalTypes import FinSwapTypes
from ...market.curves.FinDiscountCurve import FinDiscountCurve

##########################################################################

class FinFixedLeg(object):
    ''' Class for managing the fixed leg of a swap. A fixed leg is a leg with
    a sequence of flows calculated according to an ISDA schedule and with a 
    coupon that is fixed over the life of the swap. '''
    
    def __init__(self,
                 effectiveDate: FinDate,  # Date interest starts to accrue
                 endDate: (FinDate, str),  # Date contract ends
                 legType: FinSwapTypes,
                 coupon: (float),
                 freqType: FinFrequencyTypes,
                 dayCountType: FinDayCountTypes,
                 notional: float = ONE_MILLION,
                 principal: float = 0.0,
                 paymentLag: int = 0,
                 calendarType: FinCalendarTypes = FinCalendarTypes.WEEKEND,
                 busDayAdjustType: FinBusDayAdjustTypes = FinBusDayAdjustTypes.FOLLOWING,
                 dateGenRuleType: FinDateGenRuleTypes = FinDateGenRuleTypes.BACKWARD):
        ''' Create the fixed leg of a swap contract giving the contract start
        date, its maturity, fixed coupon, fixed leg frequency, fixed leg day
        count convention and notional.  '''

        checkArgumentTypes(self.__init__, locals())

        if type(endDate) == FinDate:
            self._terminationDate = endDate
        else:
            self._terminationDate = effectiveDate.addTenor(endDate)

        calendar = FinCalendar(calendarType)
        self._maturityDate = calendar.adjust(self._terminationDate,
                                             busDayAdjustType)

        if effectiveDate > self._maturityDate:
            raise FinError("Effective date after maturity date")

        self._effectiveDate = effectiveDate
        self._endDate = endDate
        self._legType = legType
        self._freqType = freqType
        self._paymentLag = paymentLag
        self._notional = notional
        self._principal = principal
        self._coupon = coupon

        self._dayCountType = dayCountType
        self._calendarType = calendarType
        self._busDayAdjustType = busDayAdjustType
        self._dateGenRuleType = dateGenRuleType

        self._startAccruedDates = []
        self._endAccruedDates = []
        self._paymentDates = []
        self._payments = []
        self._yearFracs = []
        self._accruedDays = []
        self._rates = []

        self.generatePayments()

###############################################################################

    def generatePayments(self):
        # These are generated immediately as they are for the entire
        # life of the swap. Given a valuation date we can determine
        # which cash flows are in the future and value the swap
        # The schedule allows for a specified lag in the payment date
        scheduleDates = FinSchedule(self._effectiveDate,
                                    self._terminationDate,
                                    self._freqType,
                                    self._calendarType,
                                    self._busDayAdjustType,
                                    self._dateGenRuleType)._generate()

        if len(scheduleDates) < 2:
            raise FinError("Schedule has none or only one date")

        self._startAccruedDates = []
        self._endAccruedDates = []
        self._paymentDates = []
        self._yearFracs = []
        self._accruedDays = []
        self._rates = []

        prevDt = scheduleDates[0] 
        
        dayCounter = FinDayCount(self._dayCountType)
        calendar = FinCalendar(self._calendarType)

        for nextDt in scheduleDates[1:]:

            self._startAccruedDates.append(prevDt)
            self._endAccruedDates.append(nextDt)

            if self._paymentLag == 0:
                paymentDate = nextDt
            else:
                paymentDate = calendar.addBusinessDays(nextDt, 
                                                       self._paymentLag)

            self._paymentDates.append(paymentDate)

            (yearFrac, num, den) = dayCounter.yearFrac(prevDt,
                                                       nextDt)

            self._rates.append(self._coupon)

            payment = yearFrac * self._notional * self._coupon

            self._payments.append(payment)
            self._yearFracs.append(yearFrac)
            self._accruedDays.append(num)

            prevDt = nextDt

###############################################################################

    def value(self, 
              valuationDate: FinDate,
              discountCurve: FinDiscountCurve):

        self._paymentDfs = []
        self._paymentPVs = []
        self._cumulativePVs = []
                
        notional = self._notional
        dfValue = discountCurve.df(valuationDate)
        legPV = 0.0
        numPayments = len(self._paymentDates)
 
        for iPmnt in range(0, numPayments):
 
            pmntDate = self._paymentDates[iPmnt]
            pmntAmount= self._payments[iPmnt]

            if pmntDate > valuationDate:

                dfPmnt = discountCurve.df(pmntDate) / dfValue
                pmntPV = pmntAmount * dfPmnt
                legPV += pmntPV
                
                self._paymentDfs.append(dfPmnt)            
                self._paymentPVs.append(pmntAmount*dfPmnt)
                self._cumulativePVs.append(legPV)

            else:

                self._paymentDfs.apppend(0.0)            
                self._paymentPVs.append(0.0)
                self._cumulativePVs.append(0.0)

        if pmntDate > valuationDate:
            paymentPV = self._principal * dfPmnt * notional
            self._paymentPVs[-1] += paymentPV
            legPV += paymentPV
            self._cumulativePVs[-1] = legPV

        if self._legType == FinSwapTypes.PAY:
            legPV = legPV * (-1.0)

        return legPV

##########################################################################

    def printPayments(self):
        ''' Prints the fixed leg dates, accrual factors, discount factors,
        cash amounts, their present value and their cumulative PV using the
        last valuation performed. '''

        print("START DATE:", self._effectiveDate)
        print("MATURITY DATE:", self._maturityDate)
        print("COUPON (%):", self._coupon * 100)
        print("FREQUENCY:", str(self._freqType))
        print("DAY COUNT:", str(self._dayCountType))

        if len(self._payments) == 0:
            print("Payments not calculated.")
            return

        header = "PAY_DATE     ACCR_START   ACCR_END      DAYS  YEARFRAC"
        header += "    RATE      PAYMENT "
        print(header)

        numFlows = len(self._paymentDates) 
        
        for iFlow in range(0, numFlows):
            print("%11s  %11s  %11s  %4d  %8.6f  %8.6f  %11.2f" %
                  (self._paymentDates[iFlow],
                   self._startAccruedDates[iFlow],
                   self._endAccruedDates[iFlow],
                   self._accruedDays[iFlow],
                   self._yearFracs[iFlow],
                   self._rates[iFlow] * 100.0,
                   self._payments[iFlow]))

###############################################################################

    def printValuation(self):
        ''' Prints the fixed leg dates, accrual factors, discount factors,
        cash amounts, their present value and their cumulative PV using the
        last valuation performed. '''

        print("START DATE:", self._effectiveDate)
        print("MATURITY DATE:", self._maturityDate)
        print("COUPON (%):", self._coupon * 100)
        print("FREQUENCY:", str(self._freqType))
        print("DAY COUNT:", str(self._dayCountType))

        if len(self._payments) == 0:
            print("Payments not calculated.")
            return

        header = "PAY_DATE     ACCR_START   ACCR_END     DAYS  YEARFRAC"
        header += "    RATE      PAYMENT       DF          PV        CUM PV"
        print(header)

        numFlows = len(self._paymentDates) 
        
        for iFlow in range(0, numFlows):
            print("%11s  %11s  %11s  %4d  %8.6f  %8.5f  % 11.2f  %10.8f  % 11.2f  % 11.2f" %
                  (self._paymentDates[iFlow],
                   self._startAccruedDates[iFlow],
                   self._endAccruedDates[iFlow],
                   self._accruedDays[iFlow],
                   self._yearFracs[iFlow],
                   self._rates[iFlow] * 100.0,
                   self._payments[iFlow], 
                   self._paymentDfs[iFlow],
                   self._paymentPVs[iFlow],
                   self._cumulativePVs[iFlow]))

##########################################################################

    def __repr__(self):
        s = labelToString("OBJECT TYPE", type(self).__name__)
        s += labelToString("START DATE", self._effectiveDate)
        s += labelToString("TERMINATION DATE", self._terminationDate)
        s += labelToString("MATURITY DATE", self._maturityDate)
        s += labelToString("NOTIONAL", self._notional)
        s += labelToString("PRINCIPAL", self._principal)
        s += labelToString("LEG TYPE", self._legType)
        s += labelToString("COUPON", self._coupon)
        s += labelToString("FREQUENCY", self._freqType)
        s += labelToString("DAY COUNT", self._dayCountType)
        s += labelToString("CALENDAR", self._calendarType)
        s += labelToString("BUS DAY ADJUST", self._busDayAdjustType)
        s += labelToString("DATE GEN TYPE", self._dateGenRuleType)
        return s

###############################################################################

    def _print(self):
        ''' Print a list of the unadjusted coupon payment dates used in
        analytic calculations for the bond. '''
        print(self)

###############################################################################
