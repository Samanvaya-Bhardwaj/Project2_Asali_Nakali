# Prompt 16: a registered medicine shown as fake

> databases / 2 pc's are connected, http://192.168.52.152:8011 and http://192.168.52.111:8012, but
> when we are adding a new medicine from the databases page, and then trying to check it on
> matching and cleaning phase we are unable to detect the medicine, it is saying fake... can you
> run the test properly and made the changes if you find the issue

What changed (details in part 3, changes 25–28):

* Codes are stored in the registry in standard form (`MED-sam-001` becomes `MED-SAM-001`).
  Lookups tidy what is typed, so a lower-case registration could never be found.
* "Register a new medicine" builds its row ids from the whole code, so `MED-SAM-001` and
  `MED-ABC-001` no longer collide on the registration number.
* Typing your own code over an example on Matching & cleaning clears the example's pharmacy,
  price, date and label, which described a different sale and made the new product read as fake.
* A registered code whose other details do not fit is shown in amber with a plain warning.
