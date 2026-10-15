// Used only when Docker initializes a new MongoDB volume.
db.getSiblingDB('makanwhere_demo').createUser({
  user: 'makanwhere',
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: ['readWrite', 'dbAdmin']
});
