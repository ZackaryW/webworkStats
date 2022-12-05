# webworkStats
This is a simple webwork parser that gets all the grade information

# Structure
## Webwork2Client
* each instance of this class represents a single webwork course. It has a list of all the assignments.
* `login(username, password)` - Logs into webwork2 and saves the session cookie
* `_make_request` - this method automatically handles the cookie extraction and injection

## Webwork2Obj
* a parent class for `Problem` and `Section`

## WebworkObjMeta
* a metaclass for `Webwork2Obj`
* all `Webwork2Obj` classes are linked to a `Webwork2Client` instance

