odoo.define('voip.core', function(require) {
"use strict";

var core = require('web.core');
var Model = require('web.Model');
var Class = core.Class;
var mixins = core.mixins;
var _t = core._t;

var UserAgent = Class.extend(core.mixins.PropertiesMixin,{
    init: function(parent,options){
        core.mixins.PropertiesMixin.init.call(this,parent);
        this.onCall = false;
        new Model("voip.configurator").call("get_pbx_config").then(_.bind(this.init_ua,this));
        this.blocked = false;
    },

    //initialisation of the ua object
    init_ua: function(result){
        this.mode = result.mode;
        var ua_config = {};
        if(this.mode == "prod" && !(result.login && result.pbx_ip && result.password)){
            this.trigger_error(_t('One or more parameter is missing. Please check your configuration.'));
            return;
        }
        ua_config = {
            uri: result.login +'@'+result.pbx_ip,
            wsServers: result.wsServer || null,
            authorizationUser: result.login,
            password: result.password,
            hackIpInContact: true,
            log: {level: "debug"},
            traceSip: false,
        };
        this.always_transfer = result.always_transfer;
        this.external_phone = result.external_phone;
        this.ring_number = result.ring_number;
        try{
            if(this.mode == "prod"){
                //test the ws uri
                var test_ws = new window.WebSocket(result.wsServer, 'sip');
                var self = this;
                test_ws.onerror = function(){
                    self.trigger_error(_t('The websocket uri could be wrong. Please check your configuration.'));
                };
            }
            this.ua = new SIP.UA(ua_config);
        }catch(err){
            this.trigger_error(_t('The server configuration could be wrong. Please check your configuration.'));
            return;
        }
        this.remote_audio = document.createElement("audio");
        this.remote_audio.autoplay = "autoplay";
        $("body").append(this.remote_audio);
        this.ringbacktone = document.createElement("audio");
        this.ringbacktone.loop = "true";
        this.ringbacktone.src = "/voip/static/src/sounds/ringbacktone.mp3";
        $("body").append(this.ringbacktone);
    },

    trigger_error: function(msg, temporary){
        this.trigger('sip_error', msg, temporary);
        this.blocked = true;
    },

    _make_call: function() {
        if(this.sip_session){
            return;
        }
        var call_options = {
            media: {
                stream: this.media_stream,
                render: {
                    remote: {
                        audio: this.remote_audio
                    },
                }
            }
        };    
        try{
            //Make the call
            this.sip_session = this.ua.invite(this.current_number,call_options);
        }catch(err){
            this.trigger_error(_t('the connection cannot be made. ')+
                _t('Please check your configuration.</br> (Reason receives :') + response.reason_phrase+')');
            return;
        }
        this.ua.on('invite', function (invite_session){
            console.log(invite_session.remoteIdentity.displayName);
            var confirmation = confirm(_t("Incomming call from ") + invite_session.remoteIdentity.displayName);
            if(confirmation){
                invite_session.accept(call_options);
            }else{
                invite_session.reject();
            }
        });
        //Bind action when the call is answered
        this.sip_session.on('accepted',_.bind(this.accepted,this));
        //Bind action when the call is in progress to catch the ringing phase
        this.sip_session.on('progress', _.bind(this.progress,this));
        //Bind action when the call is rejected by the customer
        this.sip_session.on('rejected',_.bind(this.rejected,this));
        //Bind action when the call is transfered
        this.sip_session.on('refer',function(response){console.log("REFER");console.log(response);});
        //Bind action when the user hangup the call while ringing
        this.sip_session.on('cancel',_.bind(this.cancel,this));
        //Bind action when the call is hanged up
        this.sip_session.on('bye',_.bind(this.bye,this));
    },

    rejected: function(response){
        this.sip_session = false;
        clearTimeout(this.timer);
        this.trigger('sip_rejected');
        this.ringbacktone.pause();
        if(response.status_code == 404 || response.status_code == 488){
            this.trigger_error(
                _.str(_t('The user credentials could be wrong or the connection cannot be made. Please check your configuration.</br> (Reason receives :%d',
                    response.reason_phrase)),
                true);
        }
    },

    bye: function(){
        clearTimeout(this.timer);
        this.sip_session = false;
        this.onCall = false;
        this.trigger('sip_bye');
        if(this.mode == "demo"){
            clearTimeout(this.timer_bye);
        }
    },

    cancel: function(){
        this.sip_session = false;
        this.onCall = false;
        clearTimeout(this.timer);
        this.ringbacktone.pause();
        this.trigger('sip_cancel');
        if(this.mode == "demo"){
            clearTimeout(this.timer_bye);
        }
    },

    progress: function(response){
        var self = this;
        if(response.reason_phrase == "Ringing"){
            this.trigger('sip_ringing');
            this.ringbacktone.play();
            //set the timer to stop the call if ringing too long
            this.timer = setTimeout(function(){
                self.trigger('sip_customer_unavailable');
                self.sip_session.cancel();
            },4000*self.ring_number);
        }
    },

    accepted: function(result){
        this.onCall = true;
        clearTimeout(this.timer);
        this.ringbacktone.pause();
        this.trigger('sip_accepted');
        if(this.always_transfer){
            this.sip_session.refer(this.external_phone);
        }
    },

    make_call: function(number){
        if(this.mode == "demo"){
            var response = {'reason_phrase': "Ringing"};
            var self = this;
            this.progress(response);
            var timer_accepted = setTimeout(function(){
                self.accepted(response);
            },5000);
            this.timer_bye = setTimeout(function(){
                self.bye();
            },10000);
            return;
        }
        this.current_number = number;

        //if there is already a media stream, it is reused
        if (this.media_stream) {
            this._make_call();
        } else {
            if (SIP.WebRTC.isSupported()) {
                /*      
                    WebRTC method to get a media stream      
                    The callbacks functions are getUserMediaSuccess, when the function succeed      
                    and getUserMediaFailure when the function failed
                    The _.bind is used to be ensure that the "this" in the callback function will still be the same
                    and not become the object "window"        
                */ 
                var mediaConstraints = {
                    audio: true,
                    video: false
                };
                SIP.WebRTC.getUserMedia(mediaConstraints, _.bind(media_stream_success,this), _.bind(no_media_stream,this));
            }else{
                this.trigger_error(_t('Your browser could not support WebRTC. Please check your configuration.'));
            }
        }
        function media_stream_success(stream){
            this.media_stream = stream;
            this._make_call();
        }
        function no_media_stream(e){
            this.trigger_error(_t('Problem during the connection. Check if the application is allowed to access your microphone from your browser.'), true);
            console.error('getUserMedia failed:', e);
        }
    },

    hangup: function(){
        if(this.mode == "demo"){
            if(this.onCall){
                this.bye();
            }else{
                this.cancel();
            }
        }
        if(this.sip_session){
            if(this.onCall){
                this.sip_session.bye();
            }else{
                this.sip_session.cancel();
            }
        }
    },

    transfer: function(number){
        if(this.sip_session){
            this.sip_session.refer(number);
        }
    },
});

return {
    UserAgent: UserAgent
};
});