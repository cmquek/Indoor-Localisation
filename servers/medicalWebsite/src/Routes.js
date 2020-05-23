import React from "react";
import { Route, Switch } from "react-router-dom";
import Home from "./Home";
import Login from "./Login";
import AddPatient from "./AddPatient";
import AddAsset from "./AddAsset";
import AddStaff from "./AddStaff";
import LocationTracking from "./LocationTracking";
import ContactTracing from "./ContactTracing";
import ContactTracingResults from "./ContactTracingResults";
import PatientInfo from "./PatientInfo";
import PatientInfo2 from "./components/patient-display/PatientInfo2";
import AssetStaffInfo from "./AssetStaffInfo"
import AddConfirmation from "./AddConfirmation"
import PatientDashboard from "./components/dashboard/PatientDashboard";

export default () =>
  <Switch>
    <Route path="/" exact component={Login} />
    <Route path="/home" exact component={Home} />
    <Route path="/addPatient" exact component={AddPatient} />
    <Route path="/editPatient" exact component={AddPatient} />
    <Route path="/addAsset" exact component={AddAsset} />
    <Route path="/addStaff" exact component={AddStaff} />
    <Route path="/locationTracking" exact component={LocationTracking} />
    <Route path="/contactTracing" exact component={ContactTracing} />
    <Route path="/contactTracingResults" exact component={ContactTracingResults} />
    <Route path="/patientInfo" exact component={PatientInfo} />
    <Route path="/patientInfo2" exact component={PatientInfo2} />
    <Route path="/staffInfo" exact component={AssetStaffInfo} />
    <Route path="/assetInfo" exact component={AssetStaffInfo} />
    <Route path="/addConfirmation" exact component={AddConfirmation} />
    <Route path="/dashboard" exact component={PatientDashboard} />
  </Switch>;
