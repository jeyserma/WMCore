"""
Unit tests for MicorService/MSUnmerged/MSUnmerged.py module

"""
from __future__ import division, print_function

import json
# system modules
import os
import unittest
import unittest.mock as mock

# WMCore modules
from WMCore.MicroService.MSUnmerged.MSUnmerged import MSUnmerged, MSUnmergedRSE
from WMCore.Services.Rucio import Rucio


def getTestFile(partialPath):
    """
    Returns the absolute path for the test json file
    """
    normPath = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
    return os.path.join(normPath, partialPath)


class RucioConMonEmul(object):
    """
    A simple class to emulate the basic behaviour of the RucioConMon Service
    """
    def __init__(self):
        super(RucioConMonEmul, self).__init__()

        self.rseUnmergedDumpFile = getTestFile('data/WMCore/MicroService/MSUnmerged/rseUnmergedDump.json')
        self.rseConsStatsDumpFile = getTestFile('data/WMCore/MicroService/MSUnmerged/rseConsStatsDump.json')
        with open(self.rseUnmergedDumpFile) as fd:
            self.rseUnmergedDump = json.load(fd)
        with open(self.rseConsStatsDumpFile) as fd:
            self.rseConsStatsDump = json.load(fd)

    def getRSEStats(self):
        """
        Emulates getting the latest statistics from the RucioConMon, together with the last
        update timestamps for all RSEs known to CMS Rucio.
        In reality it returns it from a file.
        """
        return self.rseConsStatsDump

    def getRSEUnmerged(self, rseName, zipped=False):
        """
        Emulates getting the list of all unmerged files in an RSE
        In reality it returns it from a file.
        """
        return self.rseUnmergedDump


class WMStatsServerEmul(object):
    """
    A simple class to emulate the basic behaviour of the RucioConMon Service
    """
    def __init__(self):
        super(WMStatsServerEmul, self).__init__()

        self.protectedLFNsDumpFile = getTestFile('data/WMCore/MicroService/MSUnmerged/protectedLFNsDump.json')
        with open(self.protectedLFNsDumpFile) as fd:
            self.protectedLFNsDump = json.load(fd)

    def getProtectedLFNs(self):
        return self.protectedLFNsDump


class MSUnmergedTest(unittest.TestCase):
    """ Unit test for MSUnmerged module """
    # pylint: disable=W0212,C0301

    def setUp(self):
        """ init test class """

        self.maxDiff = None

        self.msConfig = {'couch_host': 'https://cmsweb-testbed.cern.ch/couchdb',
                         'couch_wmstats_db': 'wmstats',
                         'enableRealMode': False,
                         'interval': 28800,
                         'limitRSEsPerInstance': 200,
                         'limitTiersPerInstance': ['T1', 'T2', 'T3'],
                         'limitFilesPerRSE': -1,
                         'manager': 'WMCore.MicroService.MSManager.MSManager',
                         'object': 'WMCore.MicroService.Service.RestApiHub.RestApiHub',
                         'reqmgr2Url': 'https://cmsweb-testbed.cern.ch/reqmgr2',
                         'rseExpr': 'cms_type=real&rse_type=DISK',
                         'rucioAccount': 'wmcore_transferor',
                         'rucioUrl': 'http://cmsrucio-int.cern.ch',
                         'rucioAuthUrl': 'https://cmsrucio-auth-int.cern.ch',
                         'rucioConMon': 'https://cmsweb-testbed.cern.ch/rucioconmon',
                         'services': ['unmerged'],
                         'verbose': True,
                         'wmstatsUrl': 'https://cmsweb-testbed.cern.ch/wmstatsserver'}

        self.creds = {"client_cert": os.getenv("X509_USER_CERT", "Unknown"),
                      "client_key": os.getenv("X509_USER_KEY", "Unknown")}
        self.rucioConfigDict = {"rucio_host": self.msConfig['rucioUrl'],
                                "auth_host": self.msConfig['rucioAuthUrl'],
                                "auth_type": "x509",
                                "account": self.msConfig['rucioAccount'],
                                "ca_cert": False,
                                "timeout": 30,
                                "request_retries": 3,
                                "creds": self.creds}

        self.msUnmerged = MSUnmerged(self.msConfig)
        self.msUnmerged.rucioConMon = RucioConMonEmul()
        self.msUnmerged.wmstatsSvc = WMStatsServerEmul()
        self.msUnmerged.resetCounters()
        self.msUnmerged.rucio = Rucio.Rucio(self.msConfig['rucioAccount'],
                                            hostUrl=self.rucioConfigDict['rucio_host'],
                                            authUrl=self.rucioConfigDict['auth_host'],
                                            configDict=self.rucioConfigDict)

        super(MSUnmergedTest, self).setUp()

    def testPlineUnmerged(self):
        # Test plineMSUnmerged:
        rse = MSUnmergedRSE('T2_US_Wisconsin')
        pName = self.msUnmerged.plineUnmerged.name
        self.msUnmerged.rseConsStats = self.msUnmerged.rucioConMon.getRSEStats()
        self.msUnmerged.protectedLFNs = set(self.msUnmerged.wmstatsSvc.getProtectedLFNs())
        # Emulate the pipeline run while skipping the last purgeRseObj step
        self.msUnmerged.resetCounters(plineName=pName)
        rse = self.msUnmerged.updateRSETimestamps(rse, start=True, end=False)
        rse = self.msUnmerged.consRecordAge(rse)
        rse = self.msUnmerged.getUnmergedFiles(rse)
        rse = self.msUnmerged.filterUnmergedFiles(rse)
        rse = self.msUnmerged.cleanRSE(rse)
        rse = self.msUnmerged.updateRSECounters(rse, pName)
        rse = self.msUnmerged.updateRSETimestamps(rse, start=False, end=True)
        # self.msUnmerged.plineUnmerged.run(rse)
        expectedRSE = {'counters': {'deletedFail': 0,
                                    'deletedSuccess': 0,
                                    'dirsToDelete': 6,
                                    'dirsToDeleteAll': 6,
                                    'filesToDelete': 21811,
                                    'totalNumFiles': 11938},
                       'dirs': {'allUnmerged': set(),
                                'empty': [],
                                'protected': {'/store/unmerged/RunIIAutumn18FSPremix/PMSSM_set_1_prompt_1_TuneCP2_13TeV-pythia8/AODSIM/GridpackScan_102X_upgrade2018_realistic_v15-v1',
                                              '/store/unmerged/RunIIFall17DRPremix/Suu_Diquark_S4000_chi1160_TuneCP2_13TeV-madgraph-pythia8/AODSIM/PU2017_94X_mc2017_realistic_v11-v1',
                                              '/store/unmerged/RunIIFall17DRPremix/Suu_Diquark_S4000_chi680_TuneCP2_13TeV-madgraph-pythia8/AODSIM/PU2017_94X_mc2017_realistic_v11-v1',
                                              '/store/unmerged/RunIISummer20UL16HLTAPV/QCD_Pt-20To30_MuEnrichedPt5_TuneCP5_13TeV_pythia8/GEN-SIM-RAW/80X_mcRun2_asymptotic_2016_TrancheIV_v6-v1',
                                              '/store/unmerged/RunIISummer20UL16SIMAPV/ZJetsToQQ_HT-400to600_TuneCP5_13TeV-madgraphMLM-pythia8/GEN-SIM/106X_mcRun2_asymptotic_preVFP_v8-v1'},
                                'toDelete': {'/store/unmerged/Phase2HLTTDRSummer20ReRECOMiniAOD/DYToLL_M-50_TuneCP5_14TeV-pythia8/FEVT/FlatPU0To200_pilot_111X_mcRun4_realistic_T15_v1-v2',
                                             '/store/unmerged/Run2016G/DoubleEG/MINIAOD/UL2016_MiniAODv2-v1',
                                             '/store/unmerged/SAM/testSRM/SAM-cms-lvs-gridftp.hep.wisc.edu',
                                             '/store/unmerged/SAM/testSRM/SAM-cms-lvs-gridftp.hep.wisc.edu/lcg-util',
                                             '/store/unmerged/SAM/testSRM/SAM-cmssrm.hep.wisc.edu',
                                             '/store/unmerged/SAM/testSRM/SAM-cmssrm.hep.wisc.edu/lcg-util'}},
                       'files': {'allUnmerged': mock.ANY,
                                 'deletedFail': [],
                                 'deletedSuccess': [],
                                 'protected': {},
                                 'toDelete': {'/store/unmerged/Phase2HLTTDRSummer20ReRECOMiniAOD/DYToLL_M-50_TuneCP5_14TeV-pythia8/FEVT/FlatPU0To200_pilot_111X_mcRun4_realistic_T15_v1-v2': mock.ANY,
                                              '/store/unmerged/Run2016G/DoubleEG/MINIAOD/UL2016_MiniAODv2-v1': mock.ANY,
                                              '/store/unmerged/SAM/testSRM/SAM-cms-lvs-gridftp.hep.wisc.edu': mock.ANY,
                                              '/store/unmerged/SAM/testSRM/SAM-cms-lvs-gridftp.hep.wisc.edu/lcg-util': mock.ANY,
                                              '/store/unmerged/SAM/testSRM/SAM-cmssrm.hep.wisc.edu': mock.ANY,
                                              '/store/unmerged/SAM/testSRM/SAM-cmssrm.hep.wisc.edu/lcg-util': mock.ANY}},
                       'isClean': False,
                       'name': 'T2_US_Wisconsin',
                       'pfnPrefix': None}
        self.assertDictEqual(rse, expectedRSE)

    def testCutPath(self):
        filePath = '/store/unmerged/SAM/testSRM/SAM-cmssrm.hep.wisc.edu/lcg-util/testfile-put-nospacetoken-1502337521-08cc70247c3f.txt'
        expectedFilePath = '/store/unmerged/SAM/testSRM/SAM-cmssrm.hep.wisc.edu/lcg-util'
        self.assertEqual(self.msUnmerged._cutPath(filePath), expectedFilePath)

        filePath = '/store/unmerged/SAM/testSRM/'
        expectedFilePath = '/store/unmerged/SAM/testSRM'
        self.assertEqual(self.msUnmerged._cutPath(filePath), expectedFilePath)

        filePath = '/store/unmerged/RunIIAutumn18FSPremix/PMSSM_set_1_prompt_1_TuneCP2_13TeV-pythia8/AODSIM/GridpackScan_102X_upgrade2018_realistic_v15-v1/00001/2A335139-C39F-F94C-9D06-D0D32296C62E.root'
        expectedFilePath = '/store/unmerged/RunIIAutumn18FSPremix/PMSSM_set_1_prompt_1_TuneCP2_13TeV-pythia8/AODSIM/GridpackScan_102X_upgrade2018_realistic_v15-v1'
        self.assertEqual(self.msUnmerged._cutPath(filePath), expectedFilePath)
