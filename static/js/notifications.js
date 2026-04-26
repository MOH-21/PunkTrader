/**
 * Browser notifications for alerts.
 */

function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

function sendBrowserNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body: body,
            icon: '/static/css/app.css',  // placeholder
            silent: false,
        });
    }
}

// Request on load
requestNotificationPermission();
