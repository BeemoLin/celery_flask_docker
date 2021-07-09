from time import sleep
from flask import Flask
from flask_restful import Resource, Api
from celery import Celery
from celery.signals import worker_ready, worker_shutting_down

def make_celery(app):
    print('create celery app: {}'.format(app.import_name))
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL'],
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# create flask app
flask_app = Flask('app')
flask_app.config.update(
    CELERY_BROKER_URL='redis://redis:6379',
    CELERY_RESULT_BACKEND='redis://redis:6379',
    #CELERY_IMPORTS=['comm.tasks']
)

#create celery app
celery_app = make_celery(flask_app)

# restful API
api = Api(flask_app)

# set a task
@celery_app.task
def add_together(a, b):
    sleep(10)
    return a + b

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    print('@worker_ready {}'.format(sender))
    print(celery_app.amqp.queues.keys())

@worker_shutting_down.connect
def worker_shutting_down_handler(sig, how, exitcode, **kwargs):
    print('@worker_shutting_down {} {} {}'.format(sig, how, exitcode))
    print(celery_app.amqp.queues.keys())

# set an API
class TASK(Resource):
    def get(self, queue_name='default_queue'):
        result = add_together.apply_async((23, 42), queue=queue_name)
        return {'task_{}'.format(result.task_id): 'sended'}

api.add_resource(TASK, '/send_task/<string:queue_name>')

if __name__ == '__main__':
    flask_app.run(host="0.0.0.0", debug=True)

